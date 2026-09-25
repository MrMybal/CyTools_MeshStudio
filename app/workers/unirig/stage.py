"""One isolated upstream pipeline stage; every writable path belongs to the job.

Ported from CyTools_UniRig. Each stage runs in its own process because the upstream entry
points call sys.exit and reconfigure logging; the adaptations below are applied in memory so
that the checkout stays pristine:

* ``src/model/unirig_skin.py`` imports FlashAttention, which has no wheel for this ABI. The
  import is dropped and ``attention.MHA`` — the same cross-attention built on PyTorch SDPA,
  checkpoint compatible — is injected in its place.
* ``src/system/ar.py`` only exports its npz outside "user mode"; the condition is relaxed so
  that a normal run writes them.
"""
import os,sys,runpy,json
from pathlib import Path

WORKERS = Path(__file__).resolve().parents[1]
ROOT = WORKERS.parent.parent
SOURCE = Path(os.environ.get('MESHSTUDIO_UNIRIG_SOURCE') or (ROOT/'runtime'/'sources'/'UniRig'))
DATA = ROOT/'data'
def main():
    action=sys.argv[1]; args=sys.argv[2:]
    sys.path.insert(0,str(SOURCE))
    if action=='extract':
        sys.argv=['extract',*args];runpy.run_module('src.data.extract',run_name='__main__')
    elif action=='predict':
        # Upstream module is adapted in memory; pristine source and checkpoint names preserved.
        import types
        from unirig.attention import MHA
        filename=SOURCE/'src/model/unirig_skin.py'
        module=types.ModuleType('src.model.unirig_skin');module.__file__=str(filename)
        module.__package__='src.model';module.MHA=MHA
        sys.modules[module.__name__]=module
        exec(compile(filename.read_text().replace('from flash_attn.modules.mha import MHA',''),str(filename),'exec'),module.__dict__)
        filename=SOURCE/'src/system/ar.py'
        module=types.ModuleType('src.system.ar');module.__file__=str(filename);module.__package__='src.system'
        sys.modules[module.__name__]=module
        exec(compile(filename.read_text().replace('if not self.user_mode and self.export_npz is not None:', 'if self.export_npz is not None:'),str(filename),'exec'),module.__dict__)
        sys.argv=['run.py',*args];runpy.run_path(str(SOURCE/'run.py'),run_name='__main__')
    elif action=='export':
        import numpy as np
        from src.data.raw_data import RawData,RawSkin
        folder=Path(args[0]); output=Path(args[1]); original=args[2]
        skeleton=RawData.load(str(folder/'predict_skeleton.npz'))
        skin=RawSkin.load(str(folder/'predict_skin.npz'))
        joints=np.asarray(skin.joints); weights=np.asarray(skin.skin)
        parents=np.array([-1 if x is None else int(x) for x in skeleton.parents],dtype=np.int32)
        if weights.ndim!=2 or weights.shape!=(len(skin.vertices),len(joints)): raise ValueError('Invalid weight dimensions')
        if not np.isfinite(weights).all() or weights.min() < -1e-5: raise ValueError('Invalid weights')
        totals=weights.sum(axis=1)
        if (totals<=0).any(): raise ValueError('Unweighted vertices')
        weights=weights/totals[:,None]
        np.savez_compressed(output/'rig.npz',vertices=skin.vertices,joints=joints,parents=parents,weights=weights)
        report={'vertices':len(weights),'bones':len(joints),'weights_shape':list(weights.shape),'max_weight_sum_error':float(abs(weights.sum(1)-1).max()),'joints':joints.tolist(),'parents':parents.tolist()}
        (output/'skeleton.json').write_text(json.dumps(report,indent=2))
        from src.inference.merge import merge
        merge(path=original,output_path=str(output/'rigged.glb'),vertices=skin.vertices,joints=joints,skin=weights,parents=skeleton.parents,names=skeleton.names,tails=skeleton.tails,add_root=False,is_vrm=False)
    else: raise ValueError(action)
if __name__=='__main__': main()
