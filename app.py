from flask import Flask, request, redirect, url_for, send_from_directory, render_template, flash, Response
from flask_socketio import SocketIO, emit
import os
import zipfile
import time

app = Flask(__name__)
socketio = SocketIO(app)
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024 * 1024  # 2 GB limit
app.secret_key = 'supersecretkey'

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        
        if file:
            filename = file.filename
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            content_length = file.content_length

            # Save the file and emit progress
            with open(file_path, 'wb') as f:
                chunk_size = 1024 * 1024  # 1 MB chunks
                total_size = 0
                for chunk in file.stream:
                    f.write(chunk)
                    total_size += len(chunk)
                    
                    if content_length and content_length > 0:
                        progress = total_size / content_length * 100
                    else:
                        progress = (total_size / (total_size + chunk_size)) * 100 if total_size > 0 else 0
                    
                    socketio.emit('upload_progress', {'progress': progress})
            
            if filename.endswith('.zip'):
                with zipfile.ZipFile(file_path, 'r') as zip_ref:
                    zip_ref.extractall(app.config['UPLOAD_FOLDER'])
                os.remove(file_path)
            return redirect(url_for('list_files'))
    return render_template('upload.html')

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file_size = os.path.getsize(file_path)
    
    def generate():
        with open(file_path, 'rb') as f:
            chunk_size = 1024 * 1024  # 1 MB chunks
            bytes_sent = 0
            while chunk := f.read(chunk_size):
                bytes_sent += len(chunk)
                progress = bytes_sent / file_size * 100
                socketio.emit('download_progress', {'progress': progress})
                yield chunk
                time.sleep(0.1)  # Simulate delay for demo purposes
    
    return Response(generate(), mimetype='application/octet-stream', headers={"Content-Disposition": f"attachment; filename={filename}"})

@app.route('/files')
def list_files():
    files = []
    for root, dirs, filenames in os.walk(app.config['UPLOAD_FOLDER']):
        for filename in filenames:
            file_path = os.path.relpath(os.path.join(root, filename), app.config['UPLOAD_FOLDER'])
            files.append(file_path)
    return render_template('files.html', files=files)

@app.errorhandler(413)
def request_entity_too_large(error):
    return "File Too Large", 413

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=9000, debug=True)
