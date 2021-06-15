from flask import Flask, render_template, request, redirect, url_for, abort
from selenium import webdriver
from bs4 import BeautifulSoup
import urllib.request
import requests
import urllib
import time
import os
import uuid

from flask_socketio import SocketIO


app = Flask(__name__)
socketio = SocketIO(app)

# Find the downloads folder in the user's operating system
if os.name == 'nt':
    import ctypes
    from ctypes import windll, wintypes
    from uuid import UUID

    # ctypes GUID copied from MSDN sample code
    class GUID(ctypes.Structure):
        _fields_ = [
            ("Data1", wintypes.DWORD),
            ("Data2", wintypes.WORD),
            ("Data3", wintypes.WORD),
            ("Data4", wintypes.BYTE * 8)
        ]

        def __init__(self, uuidstr):
            uuid = UUID(uuidstr)
            ctypes.Structure.__init__(self)
            self.Data1, self.Data2, self.Data3, \
                self.Data4[0], self.Data4[1], rest = uuid.fields
            for i in range(2, 8):
                self.Data4[i] = rest>>(8-i-1)*8 & 0xff

    SHGetKnownFolderPath = windll.shell32.SHGetKnownFolderPath
    SHGetKnownFolderPath.argtypes = [
        ctypes.POINTER(GUID), wintypes.DWORD,
        wintypes.HANDLE, ctypes.POINTER(ctypes.c_wchar_p)
    ]

    def _get_known_folder_path(uuidstr):
        pathptr = ctypes.c_wchar_p()
        guid = GUID(uuidstr)
        if SHGetKnownFolderPath(ctypes.byref(guid), 0, 0, ctypes.byref(pathptr)):
            raise ctypes.WinError()
        return pathptr.value

    FOLDERID_Download = '{374DE290-123F-4565-9164-39C4925E467B}'

    downloads_path = _get_known_folder_path(FOLDERID_Download)
else:
    home = os.path.expanduser("~")
    downloads_path = os.path.join(home, "Downloads")


def get_images(uri, uid):
    try:
        # Wait until the client is redirected and the page should be loaded.
        time.sleep(2)
        socketio.emit(
    		str(uid),
    		{
                'state': 'pending',
                'progress': 0,
    			'message': f'Reading the images from {uri}'
    		},
    		namespace='/proc'
    	)

        # Initialize driver and configure window.
        driver = webdriver.Chrome(executable_path="/Users/matt/Python/chromedriver")
        driver.get(uri)
        driver.maximize_window()
        driver.set_window_position(0, 800)

        # Scroll down 60 times and wait until the pictures should be loaded.
        n = 60
        for i in range(n, 0, -2):
            socketio.emit(
        		str(uid),
        		{
                    'state': 'pending',
                    'progress': int((n-i)/n*100),
        			'message': f'Seconds left: {i}'
        		},
        		namespace='/proc'
        	)
            driver.execute_script(f'window.scrollBy(0,document.body.scrollHeight)')
            time.sleep(2)

        # Extract the image addresses and close the driver's session.
        socketio.emit(
    		str(uid),
    		{
                'state': 'pending',
                'progress': 0,
    			'message': f'Downloading images...'
    		},
    		namespace='/proc'
    	)
        page = driver.page_source
        soup = BeautifulSoup(page, features='html.parser')
        srcs = [img['src'].replace('236x', 'originals') \
            for img in soup.findAll('img', 'GrowthUnauthPinImage__Image') \
            if img['src']]
        time.sleep(2)
        driver.quit()

        # Download all images found.
        socketio.emit(
    		str(uid),
    		{
                'state': 'pending',
                'progress': 0,
    			'message': f'downloading {len(srcs)} images'
    		},
    		namespace='/proc'
    	)
        for i,src in enumerate(srcs):
            dst = os.path.join(downloads_path, f'img_{i}.jpg')
            print(f'{src} -> {dst}')
            socketio.emit(
        		str(uid),
        		{
                    'state': 'pending',
                    'progress': int(i/len(srcs)*100),
        			'message': f'downloading image {src}'
        		},
        		namespace='/proc'
        	)
            try:
                urllib.request.urlretrieve(src, dst)
            except urllib.error.HTTPError:
                pass
    finally:
        socketio.emit(
    		str(uid),
    		{
                'state': 'done',
                'progress': 100,
    			'message': 'download finished'
    		},
    		namespace='/proc'
    	)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/', methods=['POST'])
def submit():
    uri = request.form['url']
    if not uri:
        return redirect(url_for('index'))
    # Generate a random unique id.
    uid = uuid.uuid4()
    # Start a background thread.
    thread = socketio.start_background_task(get_images, uri, uid)
    # Redirect the client to the next page.
    # (Not absolutely necessary if AJAX is used.)
    return redirect(url_for('download', uid=uid))

@app.route('/download')
def download():
    uid = request.args.get('uid')
    if not uid:
        return redirect(url_for('index'))
    return render_template('download.html', uid=uid)


if __name__ == "__main__":
    app.run(debug=True)
