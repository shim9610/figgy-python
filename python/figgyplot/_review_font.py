"""Resolve the actual installed UI face and carry it to notebook browsers."""
from functools import lru_cache
import struct


@lru_cache(maxsize=8)
def font_data(family):
    from ._native import review_font_data
    data,index=review_font_data(family)
    data=bytes(data)
    if data[:4]!=b'ttcf':return data
    # A browser FontFace consumes a standalone SFNT. Preserve the selected TTC
    # face, including CJK regional glyph forms, rather than silently using face 0.
    offset=struct.unpack_from('>I',data,12+4*index)[0]
    header=data[offset:offset+12]
    count=struct.unpack_from('>H',header,4)[0]
    directory=bytearray();payload=bytearray();cursor=12+16*count;head=None
    for i in range(count):
        tag,checksum,start,size=struct.unpack_from('>4sIII',data,offset+12+16*i)
        table=bytearray(data[start:start+size])
        if tag==b'head':table[8:12]=b'\0'*4;head=cursor+8
        padded=table+b'\0'*((-len(table))%4)
        checksum=sum(struct.unpack('>'+str(len(padded)//4)+'I',padded))&0xffffffff
        directory+=struct.pack('>4sIII',tag,checksum,cursor,size)
        payload+=padded;cursor+=len(padded)
    result=bytearray(header)+directory+payload
    if head is not None:
        checksum=sum(struct.unpack('>'+str(len(result)//4)+'I',result))&0xffffffff
        struct.pack_into('>I',result,head,(0xB1B0AFBA-checksum)&0xffffffff)
    return bytes(result)
