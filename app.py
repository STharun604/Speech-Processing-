from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
import os
import json
from werkzeug.utils import secure_filename
from processing import process_audio_pipeline

app = Flask(__name__)
app.config['SECRET_KEY'] = 'divide_conquer_secret_key'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///audio_stats.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class AudioRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(150), nullable=False)
    duration = db.Column(db.Float, nullable=False)
    num_segments = db.Column(db.Integer, nullable=False)
    processing_time = db.Column(db.Float, nullable=False)
    accuracy = db.Column(db.String(50), nullable=False)
    transcription = db.Column(db.Text, nullable=True)
    details_json = db.Column(db.Text, nullable=True)

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/learn-more')
def learn_more():
    return render_template('learn_more.html')

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        if 'audio_file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        file = request.files['audio_file']
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        if file:
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            # Process Audio
            try:
                results = process_audio_pipeline(filepath)
                
                # Save to DB
                new_record = AudioRecord(
                    filename=filename,
                    duration=results['duration'],
                    num_segments=results['num_segments'],
                    processing_time=results['processing_time'],
                    accuracy=results['accuracy'],
                    transcription=results['text'],
                    details_json=json.dumps({
                        'segments': results.get('segments', []), 
                        'optimization_steps': results.get('optimization_steps', []),
                        'features': results.get('features', {}),
                        'confidence_score': results.get('confidence_score', 0.0)
                    })
                )
                db.session.add(new_record)
                db.session.commit()
                
                # We could pass the complex results dictionary to the template directly,
                # or store it in the session. For this demo, we'll pass it directly to render_template.
                return render_template('dashboard.html', 
                                       record=new_record, 
                                       results=results,
                                       filename=filename)
            except Exception as e:
                flash(f"Error processing file: {str(e)}")
                return redirect(request.url)
            
    return render_template('upload.html')

@app.route('/history')
def history():
    records = AudioRecord.query.order_by(AudioRecord.id.desc()).all()
    return render_template('history.html', records=records)

@app.route('/history/<int:record_id>')
def view_record(record_id):
    record = AudioRecord.query.get_or_404(record_id)
    details = json.loads(record.details_json) if record.details_json else {'segments': [], 'optimization_steps': []}
    results = {
        'duration': record.duration,
        'num_segments': record.num_segments,
        'processing_time': record.processing_time,
        'accuracy': record.accuracy,
        'text': record.transcription,
        'segments': details.get('segments', []),
        'optimization_steps': details.get('optimization_steps', []),
        'features': details.get('features', {}),
        'confidence_score': details.get('confidence_score', 0.0)
    }
    return render_template('dashboard.html', record=record, results=results, filename=record.filename)

@app.route('/download/transcript/<int:record_id>')
def download_transcript(record_id):
    from flask import Response
    record = AudioRecord.query.get_or_404(record_id)
    text_content = f"Transcript for {record.filename}\n\n"
    text_content += record.transcription if record.transcription else "No transcription available."
    
    return Response(
        text_content,
        mimetype="text/plain",
        headers={"Content-disposition": f"attachment; filename=transcript_{record.id}.txt"}
    )

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5000)
