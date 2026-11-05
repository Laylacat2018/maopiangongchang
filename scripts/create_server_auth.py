"""Create a private owner credential file; never print or persist plaintext passwords."""
import argparse
import getpass
import hashlib
import json
import os
from pathlib import Path
import secrets
import sys


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--file',required=True)
    parser.add_argument('--username',default='admin')
    parser.add_argument('--stdin',action='store_true',help='Read one password line from stdin for automation')
    args=parser.parse_args()
    if not args.username or ':' in args.username:parser.error('Invalid username')
    if args.stdin:password=sys.stdin.readline().rstrip('\r\n')
    else:
        password=getpass.getpass('Owner password (at least 16 characters): ')
        if password!=getpass.getpass('Confirm password: '):parser.error('Passwords do not match')
    if not 16<=len(password)<=1024:parser.error('Password length must be 16–1024 characters')
    salt=secrets.token_bytes(32)
    cfg={'username':args.username,'algorithm':'pbkdf2-sha256','iterations':600000,'salt':salt.hex(),
         'hash':hashlib.pbkdf2_hmac('sha256',password.encode('utf-8'),salt,600000).hex()}
    path=Path(args.file);path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w',encoding='utf-8') as f:json.dump(cfg,f);f.flush();os.fsync(f.fileno())
    print('Created private owner credential file (password not recorded).')


if __name__=='__main__':main()
