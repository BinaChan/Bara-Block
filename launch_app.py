#!/usr/bin/env python3
"""Launch BARA-BLOCK in the default browser with automatic port selection."""
import socket,threading,time,webbrowser,sys
from http.server import ThreadingHTTPServer
from server import Handler

def first_port():
    for port in range(8770,8795):
        with socket.socket() as sock:
            try:sock.bind(('127.0.0.1',port));return port
            except OSError:continue
    raise RuntimeError('No free port between 8770 and 8794')

def run():
    port=first_port()
    server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
    url=f'http://localhost:{port}/'
    print('\nBARA-BLOCK — Peat, Waterways and Fire')
    print('Browser:',url, '\nKeep this window open while using the map.\n')
    def launch_browser():
        time.sleep(.6)
        ok=webbrowser.open(url,new=2)
        if not ok:print('Please open this URL manually:',url,flush=True)
    threading.Thread(target=launch_browser,daemon=True).start()
    try:server.serve_forever()
    except KeyboardInterrupt:print('\nShutting down BARA-BLOCK.')
    finally:server.server_close()
if __name__=='__main__':
    try:run()
    except Exception as e:
        print('Could not start:',repr(e));input('Press Enter to close...');sys.exit(1)
