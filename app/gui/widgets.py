"""Shared widgets: file dialogs, layout helpers, and the parameter editor.

The parameter editor draws an operation's ``inputSchema`` as real controls — a file picker
for a file, a slider for a bounded number, a combo for an enum — instead of a JSON box. It is
driven by the manifest, so an operation ported from an absorbed Tool keeps every one of its
parameters without a line of UI written for it.
"""
import json
from pathlib import Path

from imgui_bundle import imgui, portable_file_dialogs as pfd

MESH_FILTER = ['Meshes', '*.glb *.gltf *.obj *.ply *.stl *.off', 'All files', '*']
IMAGE_FILTER = ['Images', '*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff', 'All files', '*']
VIDEO_FILTER = ['Videos', '*.mp4 *.mov *.mkv *.avi *.webm', 'All files', '*']
ANY_FILTER = ['All files', '*']

IMAGE_FIELDS = ('image_file', 'front', 'right', 'left', 'back', 'images', 'generated_views',
                'candidates', 'reference')
VIDEO_FIELDS = ('video',)
#: label -> (frame, id) of every combo drawn, for the interaction tests: the test engine
#: does not find a combo by its label in this build (0 of 75 were), only by its id.
COMBO_IDS = {}


def remember_combo(label):
    """Call right after a combo: records its id under its visible label."""
    COMBO_IDS[label.split('###')[0].split('##')[0]] = (imgui.get_frame_count(), imgui.get_item_id())


def filter_for(field, schema):
    kind = schema.get('x-cy-kind', '')
    if kind == 'Image' or field in IMAGE_FIELDS:
        return IMAGE_FILTER
    if kind == 'Video' or field in VIDEO_FIELDS:
        return VIDEO_FILTER
    if kind in ('File', 'Files'):
        return MESH_FILTER
    return ANY_FILTER


class Dialogs:
    """Non-blocking portable file dialogs polled every frame."""

    def __init__(self):
        self.pending = None
        self.purpose = None

    def open_file(self, purpose, title, folder='', filters=None, multiple=False):
        options = pfd.opt.multiselect if multiple else pfd.opt.none
        self.pending = pfd.open_file(title, folder or str(Path.home()), filters or MESH_FILTER, options)
        self.purpose = purpose

    def save_file(self, purpose, title, folder='', default_name='', filters=None):
        self.pending = pfd.save_file(title, str(Path(folder or Path.home()) / default_name), filters or MESH_FILTER)
        self.purpose = purpose

    def select_folder(self, purpose, title, folder=''):
        self.pending = pfd.select_folder(title, folder or str(Path.home()))
        self.purpose = purpose

    def poll(self):
        """(purpose, result) when a dialog finished, else None. result is a list or a string."""
        if self.pending is None or not self.pending.ready(0):
            return None
        result = self.pending.result()
        purpose = self.purpose
        self.pending, self.purpose = None, None
        return (purpose, result) if result else None

    @property
    def busy(self):
        return self.pending is not None


def status_line(text, error=False):
    if error:
        imgui.text_colored((1.0, 0.45, 0.4, 1.0), text)
    else:
        imgui.text_wrapped(text)


def help_marker(text):
    imgui.same_line()
    imgui.text_disabled('(?)')
    if imgui.is_item_hovered():
        imgui.set_tooltip(text)


def section(title, opened=True):
    flags = imgui.TreeNodeFlags_.default_open if opened else 0
    return imgui.collapsing_header(title, flags)


# --------------------------------------------------------------------- parameter editor

def is_advanced(schema):
    return bool((schema.get('x-cy-ui') or {}).get('advanced'))


def default_for(schema):
    if 'default' in schema:
        return schema['default']
    kind = schema.get('type')
    if kind == 'boolean':
        return False
    if kind in ('integer', 'number'):
        return schema.get('minimum', 0)
    if kind == 'array':
        return []
    if kind == 'object':
        return {}
    if schema.get('enum'):
        return schema['enum'][0]
    return ''


class ParameterEditor:
    """Draws the properties of an inputSchema and keeps their values.

    ``values`` is the live dictionary the caller submits. Files are picked through the shared
    dialog, so a click never blocks the frame: the pending purpose is ``<operation>:<field>``
    and the panel routes the answer back here through :meth:`accept_path`.
    """

    def __init__(self, dialogs, tr=lambda text: text):
        self.dialogs = dialogs
        self.tr = tr
        self.show_advanced = False
        self._object_file_keys = {}   # list field -> key of its entries that holds the file

    def accept_path(self, purpose, result, values):
        """Route a finished file dialog back into ``values``. Returns True when it matched.

        A purpose is a path: ``<owner>#images#0#file`` reaches the ``file`` key of the first
        entry of the ``images`` list. A dialog opened for a nested field therefore lands in
        that entry, not next to it at the top level.
        """
        if not purpose or '#' not in purpose:
            return False
        _owner, _, path = purpose.partition('#')
        segments = path.split('#')

        if segments[-1] == 'objects':          # "add files" on a list of objects
            field = segments[-2]
            entries = values.get(field)
            entries = list(entries) if isinstance(entries, list) else []
            key = self._object_file_keys.get(field, 'file')
            for item in (result if isinstance(result, list) else [result]):
                entries.append({key: str(item)})
            values[field] = entries
            return True

        target = values
        for segment in segments[:-1]:
            if segment.isdigit():
                index = int(segment)
                if not isinstance(target, list) or index >= len(target):
                    return False
                target = target[index]
            else:
                if not isinstance(target, dict):
                    return False
                target = target.setdefault(segment, {} if not segment.isdigit() else [])
        field = segments[-1]
        if not isinstance(target, (dict, list)):
            return False
        if isinstance(result, list) and isinstance(target.get(field), list):
            target[field] = target[field] + [str(item) for item in result]
        elif isinstance(result, list):
            target[field] = str(result[0])
        else:
            target[field] = str(result)
        return True

    def draw(self, operation, values, owner=''):
        """Draw every parameter; returns True when something changed."""
        schema = operation.get('inputSchema') or {}
        properties = schema.get('properties') or {}
        required = set(schema.get('required') or [])
        owner = owner or operation['id']
        changed = False
        ordinary = [(name, item) for name, item in properties.items() if not is_advanced(item)]
        advanced = [(name, item) for name, item in properties.items() if is_advanced(item)]

        for name, item in ordinary:
            changed |= self._field(owner, name, item, values, name in required)
        if advanced:
            imgui.separator()
            _, self.show_advanced = imgui.checkbox(self.tr('Advanced settings'), self.show_advanced)
            if self.show_advanced:
                for name, item in advanced:
                    changed |= self._field(owner, name, item, values, name in required)
        return changed

    # ------------------------------------------------------------------ one field
    def _field(self, owner, name, schema, values, required):
        imgui.push_id(f'{owner}#{name}')
        try:
            label = self.tr(schema.get('title') or name.replace('_', ' ').capitalize())
            if required:
                label += ' *'
            current = values.get(name, default_for(schema))
            kind = schema.get('x-cy-kind', '')
            kind_type = schema.get('type')
            changed = False

            if kind in ('File', 'Image', 'Video') or (kind_type == 'string' and kind == 'Directory'):
                changed = self._path_field(owner, name, schema, values, label, current, kind)
            elif kind == 'Files' or (kind_type == 'array' and (schema.get('items') or {}).get('type') == 'string'):
                changed = self._list_field(owner, name, schema, values, label, current)
            elif kind_type == 'array' and (schema.get('items') or {}).get('type') == 'object':
                changed = self._object_list_field(owner, name, schema, values, label, current)
            elif schema.get('enum'):
                choices = [str(item) for item in schema['enum']]
                index = choices.index(str(current)) if str(current) in choices else 0
                modified, index = imgui.combo(label, index, choices)
                remember_combo(label)
                if modified:
                    raw = schema['enum'][index]
                    values[name] = raw
                    changed = True
            elif kind_type == 'boolean':
                modified, value = imgui.checkbox(label, bool(current))
                if modified:
                    values[name] = value
                    changed = True
            elif kind_type == 'integer':
                changed = self._number_field(name, schema, values, label, current, integer=True)
            elif kind_type == 'number':
                changed = self._number_field(name, schema, values, label, current, integer=False)
            elif kind_type == 'object' or kind_type == 'array':
                text = current if isinstance(current, str) else json.dumps(current, ensure_ascii=False)
                modified, text = imgui.input_text_multiline(label, text, (-1, 60))
                if modified:
                    values[name] = text
                    changed = True
            elif kind == 'MultilineString':
                modified, text = imgui.input_text_multiline(label, str(current or ''), (-1, 60))
                if modified:
                    values[name] = text
                    changed = True
            else:
                modified, text = imgui.input_text(label, str(current or ''))
                if modified:
                    values[name] = text
                    changed = True

            if schema.get('description') and imgui.is_item_hovered():
                imgui.set_tooltip(self.tr(schema['description']))
            return changed
        finally:
            imgui.pop_id()

    def _path_field(self, owner, name, schema, values, label, current, kind):
        changed = False
        width = max(160.0, imgui.get_content_region_avail().x - 190.0)
        imgui.set_next_item_width(width)
        modified, text = imgui.input_text(label, str(current or ''))
        if modified:
            values[name] = text
            changed = True
        imgui.same_line()
        if imgui.button(self.tr('Browse') + f'###browse-{name}'):
            title = self.tr('Choose') + ' ' + name.replace('_', ' ')
            if kind == 'Directory':
                self.dialogs.select_folder(f'{owner}#{name}', title)
            else:
                self.dialogs.open_file(f'{owner}#{name}', title, filters=filter_for(name, schema))
        if current:
            imgui.same_line()
            if imgui.small_button(self.tr('Clear') + f'###clear-{name}'):
                values[name] = ''
                changed = True
        return changed

    def _list_field(self, owner, name, schema, values, label, current):
        changed = False
        items = list(current) if isinstance(current, list) else []
        imgui.text(label + f' ({len(items)})')
        imgui.same_line()
        if imgui.small_button(self.tr('Add') + f'###add-{name}'):
            self.dialogs.open_file(f'{owner}#{name}', self.tr('Choose files'),
                                   filters=filter_for(name, schema), multiple=True)
        if items:
            imgui.same_line()
            if imgui.small_button(self.tr('Clear') + f'###clearlist-{name}'):
                values[name] = []
                return True
        removed = None
        for index, item in enumerate(items):
            imgui.push_id(index)
            imgui.bullet_text(Path(str(item)).name)
            if imgui.is_item_hovered():
                imgui.set_tooltip(str(item))
            imgui.same_line()
            if imgui.small_button('x'):
                removed = index
            imgui.pop_id()
        if removed is not None:
            del items[removed]
            values[name] = items
            changed = True
        return changed

    def _object_list_field(self, owner, name, schema, values, label, current):
        """A list whose entries are objects: one sub-form per entry, added and removed here.

        Several ported operations take structured lists — a view carries its file, its role and
        its angles, not just a path. Falling back to a JSON box for those made the main input of
        the view operations an empty ``[]`` nobody could fill, which is what this replaces.
        """
        item_schema = schema.get('items') or {}
        properties = item_schema.get('properties') or {}
        required = set(item_schema.get('required') or [])
        maximum = schema.get('maxItems')
        items = list(current) if isinstance(current, list) else []
        changed = False

        file_key = next((key for key, value in properties.items()
                         if value.get('x-cy-kind') in ('File', 'Image', 'Video')), '')

        imgui.text(f'{label} ({len(items)})')
        if maximum is None or len(items) < maximum:
            imgui.same_line()
            if file_key and imgui.small_button(self.tr('Add files') + f'###addobj-{name}'):
                self._object_file_keys[name] = file_key
                self.dialogs.open_file(f'{owner}#{name}#objects', self.tr('Choose files'),
                                       filters=filter_for(file_key, properties[file_key]),
                                       multiple=True)
            if file_key:
                imgui.same_line()
            if imgui.small_button(self.tr('Add empty') + f'###addempty-{name}'):
                items.append({key: default_for(value) for key, value in properties.items()
                              if key in required or 'default' in value})
                values[name] = items
                changed = True
        if items:
            imgui.same_line()
            if imgui.small_button(self.tr('Clear') + f'###clearobj-{name}'):
                values[name] = []
                return True

        removed = None
        for index, entry in enumerate(items):
            if not isinstance(entry, dict):
                continue
            imgui.push_id(f'{name}-{index}')
            title = str(entry.get(file_key, '')) if file_key else ''
            title = Path(title).name if title else self.tr('Entry') + f' {index + 1}'
            opened = imgui.collapsing_header(f'{index + 1}. {title}###entry-{index}',
                                             imgui.TreeNodeFlags_.default_open if len(items) <= 3 else 0)
            imgui.indent()
            if imgui.small_button(self.tr('Remove') + f'###rmobj-{index}'):
                removed = index
            if opened:
                for key, value in properties.items():
                    changed |= self._field(f'{owner}#{name}#{index}', key, value, entry,
                                           key in required)
            imgui.unindent()
            imgui.pop_id()
        if removed is not None:
            del items[removed]
            values[name] = items
            changed = True
        return changed

    def _number_field(self, name, schema, values, label, current, integer):
        minimum = schema.get('minimum')
        maximum = schema.get('maximum')
        try:
            value = int(current) if integer else float(current)
        except (TypeError, ValueError):
            value = int(minimum or 0) if integer else float(minimum or 0.0)

        if schema.get('x-cy-kind') == 'Seed':
            return self._seed_field(name, values, label, value)

        # A slider only when the range is small enough to be usable *and* legal: Dear ImGui
        # asserts on an integer range wider than INT32_MAX/2, which is exactly what a seed
        # declares. Anything wider gets a typed field with the same clamping.
        usable = (minimum is not None and maximum is not None and maximum > minimum
                  and float(maximum) - float(minimum) <= (1_000_000 if integer else 1e9))
        if usable:
            if integer:
                modified, value = imgui.slider_int(label, value, int(minimum), int(maximum))
            else:
                modified, value = imgui.slider_float(label, value, float(minimum), float(maximum))
        else:
            if integer:
                modified, value = imgui.input_int(label, value)
            else:
                modified, value = imgui.input_float(label, value)
            if minimum is not None:
                value = max(value, int(minimum) if integer else float(minimum))
            if maximum is not None:
                value = min(value, int(maximum) if integer else float(maximum))
        if modified:
            values[name] = value
            return True
        return False

    def _seed_field(self, name, values, label, value):
        """A seed is typed, not dragged, and -1 means "draw one"."""
        width = max(120.0, imgui.get_content_region_avail().x - 200.0)
        imgui.set_next_item_width(width)
        modified, value = imgui.input_int(label, int(value))
        imgui.same_line()
        if imgui.small_button(self.tr('Random') + f'###random-{name}'):
            values[name] = -1
            return True
        if modified:
            values[name] = int(value)
            return True
        return False


def coerce(operation, values):
    """Turn the editor's values into a payload the runtime will accept.

    Empty optional fields are dropped rather than sent as empty strings: the schema of a
    ported operation often marks a view or a folder as optional, and an empty string is not
    the same as "not given".
    """
    schema = operation.get('inputSchema') or {}
    properties = schema.get('properties') or {}
    required = set(schema.get('required') or [])
    payload = {}
    for name, item in properties.items():
        if name not in values:
            continue
        value = values[name]
        if value in ('', None, []) and name not in required:
            continue
        kind = item.get('type')
        try:
            if kind == 'integer':
                payload[name] = int(value)
            elif kind == 'number':
                payload[name] = float(value)
            elif kind == 'boolean':
                payload[name] = bool(value)
            elif kind in ('object', 'array') and isinstance(value, str):
                payload[name] = json.loads(value)
            else:
                payload[name] = value
        except (TypeError, ValueError) as exc:
            raise ValueError(f'{name}: {exc}') from exc
    return payload
