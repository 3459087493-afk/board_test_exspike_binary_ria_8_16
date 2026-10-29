#!/usr/bin/env python3
"""Export binary checkpoint weights into the V1 ExSpike packed INT8 format."""
from __future__ import annotations
import hashlib, json, sys
from pathlib import Path
import numpy as np
import torch

ROOT=Path(__file__).resolve().parents[1]
CKPT=ROOT/'model'/'binary_ria_pruned_816.pth'
OUT=ROOT/'deployment'/'binary_ria_8_16_weights.npz'
MANIFEST=ROOT/'deployment'/'weights_manifest.json'

LAYERS=[
 'patch_embed.block0_conv','patch_embed.block1_conv','patch_embed.block2_conv','patch_embed.block3_conv','patch_embed.block4_conv']
for i in range(4):
    for b in ('q_conv','k_conv','v_conv','proj_conv'): LAYERS.append(f'block.{i}.attn.{b}')
    for b in ('mlp1_conv','mlp2_conv'): LAYERS.append(f'block.{i}.mlp.{b}')
LAYERS.append('head')
BNS=['patch_embed.block0_bn','patch_embed.block1_bn','patch_embed.block2_bn','patch_embed.block3_bn','patch_embed.block4_bn']
for i in range(4):
    for b in ('q_bn','k_bn','v_bn','proj_bn'): BNS.append(f'block.{i}.attn.{b}')
    for b in ('mlp1_bn','mlp2_bn'): BNS.append(f'block.{i}.mlp.{b}')


def sha(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(1<<20),b''): h.update(b)
    return h.hexdigest()


def quantize(w):
    w=np.asarray(w,dtype=np.float32)
    flat=w.reshape(w.shape[0],-1)
    max_abs=np.max(np.abs(flat),axis=1)
    scale=np.where(max_abs>0,max_abs/127.0,1.0).astype(np.float32)
    q=np.clip(np.rint(flat/scale[:,None]),-127,127).astype(np.int8)
    return q,scale


def pack_tile(q,mask):
    out_c,in_c=q.shape
    tiles=(out_c+7)//8
    padded=np.zeros((tiles*8,in_c),dtype=np.int8); padded[:out_c]=q
    selected=np.zeros((tiles*8,in_c),dtype=np.uint8)
    if mask is None: selected[:out_c]=1
    else:
        m=np.asarray(mask,dtype=bool).reshape(out_c,in_c)
        selected[:out_c]=m.astype(np.uint8)
    packed=np.zeros((tiles,in_c,16),dtype=np.uint8)
    packed[...,:8]=padded.reshape(tiles,8,in_c).transpose(0,2,1).view(np.uint8)
    flags=selected.reshape(tiles,8,in_c).transpose(0,2,1)
    packed[...,8]=np.sum(flags<<np.arange(8,dtype=np.uint8),axis=-1).astype(np.uint8)
    return packed


def main():
    raw=torch.load(CKPT,map_location='cpu',weights_only=True)
    sd=raw['state_dict']
    masks={k[:-len('.weight_mask')]:v for k,v in sd.items() if k.endswith('.weight_mask')}
    arrays={}; layers=[]; total=0
    for name in LAYERS:
        key=name.replace('.','__')
        if name=='head': weight=sd['head.weight'].numpy(); bias=sd['head.bias'].numpy(); kind='Linear'
        elif name.endswith('_conv'):
            if name.startswith('patch_embed'):
                base=name
            elif '.attn.' in name:
                base=name.replace('.weight','')
            else:
                base=name
            # checkpoint uses weight_orig/mask for pruned layers, weight otherwise
            if base+'.weight_orig' in sd:
                m=masks[base]; weight=(sd[base+'.weight_orig']*m).numpy(); mask=m.bool()
            else:
                m=None; weight=sd[base+'.weight'].numpy(); mask=None
            bias=sd.get(base+'.bias')
            bias=np.zeros(weight.shape[0],dtype=np.float32) if bias is None else bias.numpy().astype(np.float32)
            kind='Conv1d' if weight.ndim==3 else 'Conv2d'
        else:
            raise RuntimeError(name)
        # head branch handled above
        if kind=='Linear':
            mask=None
        q,scale=quantize(weight)
        packed=pack_tile(q, mask)
        deq=(q.reshape(weight.shape[0],-1)*scale[:,None]).reshape(weight.shape)
        if mask is not None:
            m2=mask.reshape(weight.shape[0],-1).numpy()
            err=deq[:, :].reshape(weight.shape[0],-1)-weight.reshape(weight.shape[0],-1)
            err=err[m2]
        else:
            err=deq.reshape(weight.shape[0],-1)-weight.reshape(weight.shape[0],-1)
        flat=weight.reshape(weight.shape[0],-1)
        arrays[key+'__packed']=packed
        arrays[key+'__weight_scale']=scale
        arrays[key+'__bias']=bias.astype(np.float32)
        total+=packed.nbytes
        layers.append({
            'name':name,'key':key,'type':kind,'sparse_8_of_16':mask is not None,
            'weight_shape':list(weight.shape),'out_features':int(weight.shape[0]),
            'in_features_flat':int(np.prod(weight.shape[1:])),'blocks':int((np.prod(weight.shape[1:])+15)//16),
            'output_tiles':int(packed.shape[0]),'packed_bytes':int(packed.nbytes),
            'scale_shape':list(scale.shape),'bias_present':bool(sd.get(name+'.bias') is not None),
            'quantization':'symmetric signed int8 per output channel',
            'rounding':'round to nearest, ties to even (numpy.rint/torch.round)',
            'saturation':'clip to [-127,127]',
            'max_abs_weight_error':float(np.max(np.abs(err))),
            'mean_abs_weight_error':float(np.mean(np.abs(err))),
            'quantization_zeroed_selected_weights':int(np.sum((flat!=0)&(q==0))) if mask is not None else 0,
        })
    for name in BNS:
        # find the BatchNorm module parameters by its exact checkpoint prefix
        prefix=name
        arrays[name.replace('.','__')+'__bn_weight']=sd[prefix+'.weight'].numpy().astype(np.float32)
        arrays[name.replace('.','__')+'__bn_bias']=sd[prefix+'.bias'].numpy().astype(np.float32)
        arrays[name.replace('.','__')+'__bn_mean']=sd[prefix+'.running_mean'].numpy().astype(np.float32)
        arrays[name.replace('.','__')+'__bn_var']=sd[prefix+'.running_var'].numpy().astype(np.float32)
        # PyTorch default eps=1e-5 for all BatchNorm modules in this checkpoint
        arrays[name.replace('.','__')+'__bn_eps']=np.asarray([1e-5],dtype=np.float32)
    np.savez_compressed(OUT,**arrays)
    manifest={
        'format_version':1,'file':OUT.name,'checkpoint':str(CKPT),
        'checkpoint_sha256':sha(CKPT),
        'architecture':'DDR-resident packed weights; V1 ExSpike matrix engine',
        'input_quantization':{'type':'dynamic symmetric int16 per accelerator invocation','scale':'max(abs(x))/32767, or 1.0 for all-zero tensor','rounding':'nearest ties-to-even','saturation':'[-32767,32767]'},
        'accumulator':{'internal':'signed 48-bit','output':'signed int32 saturating','dequantization':'int32 * input_scale * per-output weight_scale'},
        'sparse_encoding':{'structural_nm':'8:16 from checkpoint weight_mask; selected bits gate each lane','record':'8 output weights in bits0..63, eight structural flags in bits64..71','physical_word_bits':128,'physical_bytes_per_8_output_input_column':16,'compressed_nm_storage':False},
        'dense_encoding':'same 128-bit record; structural flags all valid output lanes',
        'layers':layers,'total_packed_weight_bytes':int(total),'npz_size_bytes':int(OUT.stat().st_size),'storage':'DDR; cached per layer on ARM as in V1',
        'binary_spike_semantics':'0/1, tau=2, threshold=1, hard reset',
    }
    MANIFEST.write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({'npz':str(OUT),'sha256':sha(OUT),'layers':len(layers),'packed_bytes':total,'npz_bytes':OUT.stat().st_size},indent=2))

if __name__=='__main__': main()
