"""Shared widgets: file dialogs, layout helpers, and the parameter editor.

The parameter editor draws an operation's ``inputSchema`` as real controls — a file picker
for a file, a value bar for a bounded number, a combo for an enum, a switch for an on/off
setting — instead of a JSON box. It is driven by the manifest, so an operation ported from an
absorbed Tool keeps every one of its parameters without a line of UI written for it.

Everything is drawn with CyUI (app/cyui.py, the Python port of the CyUI library): labels in
the left column of a property table, the explanation of each field behind its (i), colours
and sizes from the theme only.
"""
import json
from pathlib import Path

from imgui_bundle import imgui, portable_file_dialogs as pfd

import cyui

MESH_FILTER = ['Meshes', '*.glb *.gltf *.obj *.ply *.stl *.off', 'All files', '*']
IMAGE_FILTER = ['Images', '*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff', 'All files', '*']
VIDEO_FILTER = ['Videos', '*.mp4 *.mov *.mkv *.avi *.webm', 'All files', '*']
ANY_FILTER = ['All files', '*']

IMAGE_FIELDS = ('image_file', 'front', 'right', 'left', 'back', 'images', 'generated_views',
                'candidates', 'reference')
VIDEO_FIELDS = ('video',)
#: key -> (frame, id) of combos and custom-drawn items, for the interaction tests: the test
#: engine does not find a combo, nor an item drawn over an invisible button, by its label in
#: this build (0 of 75 combos were) — only by its id.
COMBO_IDS = {}
ITEM_IDS = COMBO_IDS
_FLT_MIN = 1.17549435e-38


def remember_combo(label):
    """Call right after a combo (or any item a test must click): records its id by its label."""
    COMBO_IDS[label.split('###')[0].split('##')[0]] = (imgui.get_frame_count(), imgui.get_item_id())


remember_item = remember_combo


def action(text, glyph, tr):
    """The label of an action button: its icon, its translated text, and a stable id.

    The id is the English text (``###Run the workflow``), so a test finds the button whatever
    the language and whether or not the icon font is installed.
    """
    shown = tr(text)
    if glyph and cyui.icons_available():
        shown = glyph + '  ' + shown
    return f'{shown}###{text}'


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


def status_line(text, error=False, tone=''):
    """A standing condition said where it applies: an error, a warning, or a plain note."""
    if not text:
        return
    if error or tone in ('error', 'warning', 'success', 'info'):
        cyui.callout(tone or 'error', text)
    else:
        imgui.push_text_wrap_pos(0.0)
        cyui.text_dim(text)
        imgui.pop_text_wrap_pos()


def help_marker(text):
    cyui.help_marker(text)


def progress(job, jobs):
    """A job's progress bar with its step and message on it."""
    value = float((job.get('progress') or {}).get('percent', 0.0)) / 100.0
    cyui.progress_bar(value if value > 0 else -1.0, (-1.0, 0.0), jobs.progress_text(job), 'accent')


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
        ordinary = [(name, item) for name, item in properties.items() if not is_advanced(item)]
        advanced = [(name, item) for name, item in properties.items() if is_advanced(item)]

        changed = self._table(f'##parameters-{owner}', owner, ordinary, values, required)
        if not ordinary and not advanced:
            cyui.text_faint(self.tr('This operation takes no parameter.'))
        if advanced:
            cyui.space(2.0)
            if cyui.begin_section(self.tr('Advanced settings'), False):
                changed |= self._table(f'##advanced-{owner}', owner, advanced, values, required)
                cyui.end_section()
        return changed

    def _table(self, identifier, owner, fields, values, required):
        if not fields or not cyui.begin_properties(identifier):
            return False
        changed = False
        for name, item in fields:
            changed |= self._field(owner, name, item, values, name in required)
        cyui.end_properties()
        return changed

    # ------------------------------------------------------------------ one field
    def _field(self, owner, name, schema, values, required):
        imgui.push_id(f'{owner}#{name}')
        try:
            label = self.tr(schema.get('title') or name.replace('_', ' ').capitalize())
            shown = label + (' *' if required else '')
            description = self.tr(schema['description']) if schema.get('description') else ''
            cyui.property(shown, description)
            current = values.get(name, default_for(schema))
            kind = schema.get('x-cy-kind', '')
            kind_type = schema.get('type')
            hidden = '##' + name

            if kind in ('File', 'Image', 'Video') or (kind_type == 'string' and kind == 'Directory'):
                return self._path_field(owner, name, schema, values, current, kind)
            if kind == 'Files' or (kind_type == 'array' and (schema.get('items') or {}).get('type') == 'string'):
                return self._list_field(owner, name, schema, values, current)
            if kind_type == 'array' and (schema.get('items') or {}).get('type') == 'object':
                return self._object_list_field(owner, name, schema, values, current)
            if schema.get('enum'):
                choices = [str(item) for item in schema['enum']]
                index = choices.index(str(current)) if str(current) in choices else 0
                modified, index = imgui.combo(hidden, index, choices)
                remember_combo(label)
                if modified:
                    values[name] = schema['enum'][index]
                return modified
            if kind_type == 'boolean':
                modified, value = cyui.toggle_switch(hidden, bool(current))
                if modified:
                    values[name] = value
                return modified
            if kind_type == 'integer':
                return self._number_field(name, schema, values, current, integer=True)
            if kind_type == 'number':
                return self._number_field(name, schema, values, current, integer=False)
            if kind_type in ('object', 'array') or kind == 'MultilineString':
                text = current if isinstance(current, str) else (
                    json.dumps(current, ensure_ascii=False) if kind_type in ('object', 'array') else str(current or ''))
                with cyui.scoped_font(cyui.mono_font() if kind_type in ('object', 'array') else None, 1.0):
                    modified, text = imgui.input_text_multiline(hidden, text, (-_FLT_MIN, cyui.dp(64.0)))
                if modified:
                    values[name] = text
                return modified
            modified, text = imgui.input_text(hidden, str(current or ''))
            if modified:
                values[name] = text
            return modified
        finally:
            imgui.pop_id()

    def _path_field(self, owner, name, schema, values, current, kind):
        changed = False
        buttons = (imgui.get_frame_height() + cyui.dp(2.0)) * (2 if current else 1) + cyui.dp(4.0)
        imgui.set_next_item_width(max(cyui.dp(80.0), imgui.get_content_region_avail().x - buttons))
        hint = self.tr('No folder chosen') if kind == 'Directory' else self.tr('No file chosen')
        modified, text = imgui.input_text_with_hint('##' + name, hint, str(current or ''))
        if current:
            cyui.tooltip(str(current))
        if modified:
            values[name] = text
            changed = True
        imgui.same_line(0.0, cyui.dp(4.0))
        if cyui.icon_button(cyui.icon.folder, self.tr('Browse')):
            title = self.tr('Choose') + ' ' + name.replace('_', ' ')
            if kind == 'Directory':
                self.dialogs.select_folder(f'{owner}#{name}', title)
            else:
                self.dialogs.open_file(f'{owner}#{name}', title, filters=filter_for(name, schema))
        if current:
            imgui.same_line(0.0, cyui.dp(2.0))
            if cyui.icon_button(cyui.icon.close, self.tr('Clear')):
                values[name] = ''
                changed = True
        return changed

    def _list_field(self, owner, name, schema, values, current):
        changed = False
        items = list(current) if isinstance(current, list) else []
        cyui.text_dim(f"{len(items)} {self.tr('file(s)')}")
        imgui.same_line()
        if cyui.button(action('Add', cyui.icon.add, self.tr) + f'-{name}', 'ghost', small=True):
            self.dialogs.open_file(f'{owner}#{name}', self.tr('Choose files'),
                                   filters=filter_for(name, schema), multiple=True)
        if items:
            imgui.same_line()
            if cyui.button(self.tr('Clear') + f'###clearlist-{name}', 'ghost', small=True):
                values[name] = []
                return True
        removed = None
        for index, item in enumerate(items):
            imgui.push_id(index)
            if cyui.icon_button(cyui.icon.close, self.tr('Remove')):
                removed = index
            imgui.same_line()
            imgui.align_text_to_frame_padding()
            imgui.text_unformatted(Path(str(item)).name)
            cyui.tooltip(str(item))
            imgui.pop_id()
        if removed is not None:
            del items[removed]
            values[name] = items
            changed = True
        return changed

    def _object_list_field(self, owner, name, schema, values, current):
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

        cyui.text_dim(f"{len(items)} {self.tr('entries')}")
        if maximum is None or len(items) < maximum:
            imgui.same_line()
            if file_key and cyui.button(action('Add files', cyui.icon.add, self.tr) + f'-{name}', 'ghost', small=True):
                self._object_file_keys[name] = file_key
                self.dialogs.open_file(f'{owner}#{name}#objects', self.tr('Choose files'),
                                       filters=filter_for(file_key, properties[file_key]),
                                       multiple=True)
            imgui.same_line()
            if cyui.button(self.tr('Add empty') + f'###addempty-{name}', 'ghost', small=True):
                items.append({key: default_for(value) for key, value in properties.items()
                              if key in required or 'default' in value})
                values[name] = items
                changed = True
        if items:
            imgui.same_line()
            if cyui.button(self.tr('Clear') + f'###clearobj-{name}', 'ghost', small=True):
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
            if cyui.button(self.tr('Remove') + f'###rmobj-{index}', 'ghost', small=True):
                removed = index
            if opened and cyui.begin_properties(f'##entry-{index}'):
                for key, value in properties.items():
                    changed |= self._field(f'{owner}#{name}#{index}', key, value, entry, key in required)
                cyui.end_properties()
            imgui.pop_id()
        if removed is not None:
            del items[removed]
            values[name] = items
            changed = True
        return changed

    def _number_field(self, name, schema, values, current, integer):
        minimum = schema.get('minimum')
        maximum = schema.get('maximum')
        try:
            value = int(current) if integer else float(current)
        except (TypeError, ValueError):
            value = int(minimum or 0) if integer else float(minimum or 0.0)

        if schema.get('x-cy-kind') == 'Seed':
            return self._seed_field(name, values, value)

        # A value bar only when the range is small enough to be usable: Dear ImGui asserts on
        # an integer range wider than INT32_MAX/2, which is exactly what a seed declares, and a
        # bar across a billion steps cannot be aimed. Anything wider gets a typed field.
        usable = (minimum is not None and maximum is not None and maximum > minimum
                  and float(maximum) - float(minimum) <= (100_000 if integer else 1e6))
        if usable:
            modified, number = cyui.slider_bar('##' + name, float(value), float(minimum), float(maximum),
                                               '%d' if integer else '%.3f', -1.0)
            value = int(round(number)) if integer else float(number)
            if modified and integer:
                modified = value != values.get(name, current)
        else:
            if integer:
                modified, value = imgui.input_int('##' + name, int(value))
            else:
                modified, value = imgui.input_float('##' + name, float(value))
            if minimum is not None:
                value = max(value, int(minimum) if integer else float(minimum))
            if maximum is not None:
                value = min(value, int(maximum) if integer else float(maximum))
        if modified:
            values[name] = value
            return True
        return False

    def _seed_field(self, name, values, value):
        """A seed is typed, not dragged, and -1 means "draw one"."""
        imgui.set_next_item_width(max(cyui.dp(80.0), imgui.get_content_region_avail().x
                                      - imgui.get_frame_height() - cyui.dp(6.0)))
        modified, value = imgui.input_int('##' + name, int(value))
        imgui.same_line(0.0, cyui.dp(4.0))
        if cyui.icon_button(cyui.icon.shuffle, self.tr('Random')):
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
