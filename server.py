from flask import Flask, render_template, send_file, request, jsonify
import json
import os
from google import genai
from dotenv import load_dotenv
import pathlib

app = Flask(__name__)

# Load API key from .env file
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError("API key not found. Make sure .env file is set correctly.")

client = genai.Client(api_key=api_key)
PDF_PATH = "03-storage1.pdf"

# Load mock slide data
def load_slide_data():
    try:
        with open('static/data/slide_texts.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {
            "1": "This is the first slide's text. It discusses database storage basics.",
            "2": "Second slide covers memory hierarchy and its importance.",
            "3": "Third slide explains disk-based architecture.",
        }

# Get overall context from all slides
def get_overall_context():
    slides = load_slide_data()
    context = "This is a lecture about Database Systems, specifically focusing on Database Storage (Files & Pages). "
    context += "The lecture covers: "
    topics = [text.split(": ", 1)[1] if ": " in text else text for text in slides.values()]
    context += ", ".join(topics[:10])  # First 10 topics for brevity
    context += "... and more topics related to database storage systems."
    return context

def get_slide_context(current_slide, slides):
    """Get context from surrounding slides."""
    slide_numbers = sorted([int(k) for k in slides.keys()])
    current_idx = slide_numbers.index(current_slide)
    
    # Get 2 slides before and after for context
    start_idx = max(0, current_idx - 2)
    end_idx = min(len(slide_numbers), current_idx + 3)
    
    context_slides = {}
    for idx in range(start_idx, end_idx):
        slide_num = slide_numbers[idx]
        context_slides[slide_num] = slides[str(slide_num)]
    
    return context_slides

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/pdf/<path:filename>')
def serve_pdf(filename):
    return send_file('03-storage1.pdf', mimetype='application/pdf')

@app.route('/slide_texts')
def get_slide_texts():
    return load_slide_data()

@app.route('/ask_gemini', methods=['POST'])
def ask_gemini():
    try:
        data = request.json
        question = data.get('question')
        current_slide = int(data.get('currentSlide'))
        
        # Upload the PDF file to Gemini
        pdf_file = client.files.upload(file=PDF_PATH)
        
        # Get slides data
        slides = load_slide_data()
        
        # Get surrounding slides for context
        context_slides = get_slide_context(current_slide, slides)
        
        # Construct context string
        slides_context = "\n".join([
            f"Slide {num}: {content}"
            for num, content in context_slides.items()
        ])
        
        # Get overall lecture context
        lecture_context = get_overall_context()
        
        # Construct prompt
        prompt = f"""This is a question about slide {current_slide} of the PDF document.

Question: {question}

Current Slide: {current_slide}

Surrounding Slides Content:
{slides_context}

Overall Lecture Context: {lecture_context}

Please focus on the content of slide {current_slide} when answering the question. You may also reference nearby slides if they provide relevant context.
Only answer based on what you can see in the actual PDF document."""

        # Call Gemini with both the PDF and the prompt
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[pdf_file, prompt]
        )
        
        return jsonify({
            'success': True,
            'response': response.text
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

if __name__ == '__main__':
    app.run(debug=True)
