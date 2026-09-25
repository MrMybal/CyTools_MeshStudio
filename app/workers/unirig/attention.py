"""Checkpoint-compatible FlashAttention cross MHA using PyTorch SDPA.
Only the cross-attention configuration used by UniRig is implemented.
"""
import torch
from torch import nn
class MHA(nn.Module):
    def __init__(self,embed_dim,num_heads,cross_attn=True):
        super().__init__()
        if not cross_attn or embed_dim%num_heads: raise ValueError('Unsupported MHA configuration')
        self.num_heads=num_heads; self.head_dim=embed_dim//num_heads
        self.Wq=nn.Linear(embed_dim,embed_dim)
        self.Wkv=nn.Linear(embed_dim,2*embed_dim)
        self.out_proj=nn.Linear(embed_dim,embed_dim)
    def forward(self,x,x_kv):
        b,n,c=x.shape
        q=self.Wq(x).reshape(b,n,self.num_heads,self.head_dim).transpose(1,2)
        k,v=self.Wkv(x_kv).reshape(b,-1,2,self.num_heads,self.head_dim).unbind(2)
        y=torch.nn.functional.scaled_dot_product_attention(q,k.transpose(1,2),v.transpose(1,2))
        return self.out_proj(y.transpose(1,2).reshape(b,n,c))
