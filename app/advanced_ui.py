"""Complete operation access for standalone users; no UI imports in the runtime."""
import json
from pathlib import Path
import sys
from concurrent.futures import ThreadPoolExecutor

PRIORITIES = ['Interactive','Critical','High','Normal','Background','Low']

class Panel:
    def __init__(self,runtime,principal=None):
        self.runtime=runtime;self.index=0;self.drafts={};self.job=None;self.message='';self.frames=0
        self.test='--ui-test-advanced' in sys.argv;self.future=None;self.executor=ThreadPoolExecutor(max_workers=1)
        if runtime is not None:
            from cytools_core.transports.api import LocalClient
            from model_options_ui import submit_exact
            self.submit=lambda *args,**kwargs:submit_exact(runtime,*args,**kwargs)
            self.principal=principal or runtime.authenticate(runtime.create_client('Standalone advanced')['token'])
            self.client=LocalClient(runtime,self.principal);self.session=runtime.create_session(self.principal, temporary=False)['sessionId']
            from ui_common import journal
            journal.bind(runtime,self.principal)
    def state(self):
        operation=self.runtime.descriptor['operations'][self.index]
        if operation['id'] not in self.drafts:
            defaults={k:v['default'] for k,v in operation['inputSchema'].get('properties',{}).items() if 'default' in v}
            self.drafts[operation['id']]={'text':json.dumps(defaults,indent=2),'backend':'','model':'','priority':3,'queue':'','execution':'','path':''}
        return operation,self.drafts[operation['id']]
    def payload(self):
        operation,state=self.state()
        from cytools_core import validate_parameters
        return validate_parameters(json.loads(state['text']),operation['inputSchema'])
    def restore(self,value):
        self.index=next(i for i,o in enumerate(self.runtime.descriptor['operations']) if o['id']==value['operationId'])
        _,state=self.state();state.update(text=json.dumps(value['parameters'],indent=2,ensure_ascii=False),backend=value.get('backendId',''),model=value.get('modelId',''))
        for key in ('priority','queue','execution'):
            if key in value.get('uiState',{}).get('invocation',{}):state[key]=value['uiState']['invocation'][key]
    def draw_tab(self):
        from ui_common import raw,label
        ui=raw();opened,_=ui.begin_tab_item(label('Advanced operations'),flags=ui.TabItemFlags_.set_selected if self.test else 0)
        if not opened:return
        try:self.draw_content()
        finally:ui.end_tab_item()
    def draw_content(self):
        """The page itself, for an interface that draws its own navigation."""
        from ui_common import raw,label,tr,ROOT,current_recipe
        import cyui
        ui=raw()
        try:
            self.frames+=1
            cyui.panel_header(tr('Advanced operations'),tr('All declared parameters are available here. This JSON takes precedence over the simplified form and model preferences.'))
            cyui.space(4.0)
            if self.runtime is None:
                cyui.empty_state(tr('Runtime unavailable'));return
            if self.future and self.future.done():
                try:self.message=json.dumps(self.future.result(),indent=2,ensure_ascii=False)
                except Exception as exc:self.message=str(exc)
                self.future=None
            if self.job:self.job=self.runtime.get_job(self.principal,self.job['jobId'])
            if cyui.begin_properties('##advanced-invocation'):
                cyui.property(tr('Operation'))
                _,self.index=ui.combo('##operation',self.index,[o['id'] for o in self.runtime.descriptor['operations']])
                operation,state=self.state()
                cyui.property(tr('Backend ID'))
                _,state['backend']=ui.input_text('##backend',state['backend'])
                cyui.property(tr('Model ID'))
                _,state['model']=ui.input_text('##model',state['model'])
                cyui.property(tr('Priority'))
                _,state['priority']=ui.combo('##priority',state['priority'],PRIORITIES)
                cyui.property(tr('Queue timeout (seconds, empty = default)'))
                _,state['queue']=ui.input_text('##queue',state['queue'])
                cyui.property(tr('Execution timeout (seconds, empty = default)'))
                _,state['execution']=ui.input_text('##execution',state['execution'])
                cyui.end_properties()
            operation,state=self.state()
            cyui.space(2.0)
            ui.push_text_wrap_pos(0.0);cyui.text_dim(operation['description']);ui.pop_text_wrap_pos()
            if cyui.button(label('Copy operation contract'),'ghost'):
                ui.set_clipboard_text(json.dumps(operation,indent=2,ensure_ascii=False));cyui.notify(tr('Copied to the clipboard'),'success')
            ui.same_line()
            if cyui.button(label('Import current form'),'ghost'):self.restore(current_recipe());operation,state=self.state()
            if cyui.begin_section(label('Full input and output schemas'),False):
                with cyui.scoped_font(cyui.mono_font(),0.95):
                    ui.input_text_multiline('##contract',json.dumps(operation,indent=2,ensure_ascii=False),ui.ImVec2(-1,180),flags=ui.InputTextFlags_.read_only)
                cyui.end_section()
            cyui.section_title(tr('Parameters JSON'))
            with cyui.scoped_font(cyui.mono_font(),0.95):
                _,state['text']=ui.input_text_multiline('##parameters-json',state['text'],ui.ImVec2(-1,200))
            if cyui.button(label('Validate and estimate')) and self.future is None:
                self.future=self.executor.submit(self.client.call,'CanRun',operationId=operation['id'],parameters=self.payload(),backendId=state['backend'],modelId=state['model'])
            ui.same_line()
            active=self.job and self.job['state'] not in ('Completed','Cancelled','Failed')
            ui.begin_disabled(bool(active))
            try:
                if cyui.primary_button(label('Run exact parameters')):
                    options={key:float(state[field]) for key,field in (('queue_timeout','queue'),('execution_timeout','execution')) if state[field].strip()}
                    self.job=self.submit(self.principal,self.session,operation['id'],self.payload(),backend_id=state['backend'],model_id=state['model'],priority=PRIORITIES[state['priority']],**options)
                    self.message=json.dumps(self.job,indent=2,ensure_ascii=False)
            finally:ui.end_disabled()
            if active:
                ui.same_line()
                if cyui.button(label('Cancel')):self.runtime.cancel(self.principal,self.job['jobId'])
            cyui.space(6.0)
            if cyui.begin_properties('##advanced-configuration'):
                cyui.property(tr('Configuration path'))
                _,state['path']=ui.input_text('##configuration-path',state['path'])
                cyui.end_properties()
            if cyui.button(label('Save exact configuration')):
                from generation_config import recipe,save
                path=Path(state['path']) if state['path'] else ROOT/'data/configurations'/(operation['id']+'-advanced.json')
                save(path,recipe(self.runtime.descriptor,operation['id'],self.payload(),backend=state['backend'],model=state['model'],ui_state={'invocation':{k:state[k] for k in ('priority','queue','execution')}}))
                state['path']=str(path);self.message=str(path)
            ui.same_line()
            if cyui.button(label('Load configuration')):
                from generation_config import load
                self.restore(load(state['path'],self.runtime.descriptor))
            if self.job:
                cyui.space(6.0)
                tone={'Completed':'success','Failed':'error','Cancelled':'warning'}.get(self.job['state'],'info')
                cyui.badge(tr(self.job['state']).upper(),tone)
                ui.same_line()
                if cyui.button(label('Copy job and outputs'),'ghost'):ui.set_clipboard_text(json.dumps(self.job,indent=2,ensure_ascii=False))
                with cyui.scoped_font(cyui.mono_font(),0.95):
                    ui.input_text_multiline('##job',json.dumps(self.job,indent=2,ensure_ascii=False),ui.ImVec2(-1,180),flags=ui.InputTextFlags_.read_only)
            if self.message:
                with cyui.scoped_font(cyui.mono_font(),0.95):
                    ui.input_text_multiline('##result',self.message,ui.ImVec2(-1,120),flags=ui.InputTextFlags_.read_only)
        except Exception as exc:self.message=str(exc)
    def close(self):
        self.executor.shutdown(wait=True,cancel_futures=True)
        if self.runtime is not None:
            try:self.runtime.close_session(self.principal,self.session)
            except Exception:pass
