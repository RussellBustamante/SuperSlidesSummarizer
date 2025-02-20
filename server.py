from flask import Flask, render_template, send_file, request, jsonify
import json
import os
from google import genai
from dotenv import load_dotenv
import pathlib
import asyncio
import threading
from app import main as process_pdf

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
            content = f.read().strip()
            if not content:
                # If the file is empty, return a default dictionary
                return {
                    "1": "Slide 1: Default Title",
                    "2": "Slide 2: Default Title",
                    "3": "Slide 3: Default Title",
                }
            return json.loads(content)
    except FileNotFoundError:
        return {
            "1": "Slide 1: Default Title",
            "2": "Slide 2: Default Title",
            "3": "Slide 3: Default Title",
        }
    except json.JSONDecodeError:
        # If file is malformed, return a default structure.
        return {
            "1": "Slide 1: Default Title",
            "2": "Slide 2: Default Title",
            "3": "Slide 3: Default Title",
        }

# Get overall context from all slides
def get_overall_context():
    slides = load_slide_data()
    context = "This is a lecture about Database Systems, specifically focusing on Database Storage (Files & Pages). "
    context += "The lecture covers: "
    topics = []
    for slide_data in slides.values():
        if isinstance(slide_data, dict):
            topics.append(slide_data.get('title', '').split(': ', 1)[-1])
        else:
            topics.append(slide_data.split(': ', 1)[-1] if ': ' in slide_data else slide_data)
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
        slide_data = slides[str(slide_num)]
        if isinstance(slide_data, dict):
            context_slides[slide_num] = f"{slide_data.get('title', '')} - {slide_data.get('summary', '')}"
        else:
            context_slides[slide_num] = slide_data
    return context_slides

def fix_json_response(text):
    """Attempt to fix malformed JSON in Gemini's response."""
    retry_prompt = f"""The following text was meant to be valid JSON but may be malformed. 
    Please carefully format it as valid JSON, preserving all the information:

    {text}

    Return ONLY the fixed JSON with no additional text or explanation."""

    try:
        # First try parsing as-is
        json.loads(text)
        return text
    except json.JSONDecodeError:
        try:
            # Try getting Gemini to fix it
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=retry_prompt
            )
            fixed_text = response.text.strip()
            # Verify the fixed version is valid JSON
            json.loads(fixed_text)
            return fixed_text
        except Exception as e:
            print(f"Error fixing JSON: {str(e)}")
            raise

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
        
        # Get slides data
        slides = load_slide_data()
        
        # Get current slide content
        current_slide_data = slides[str(current_slide)]
        if isinstance(current_slide_data, dict):
            current_slide_content = f"{current_slide_data.get('title', '')} - {current_slide_data.get('summary', '')}"
        else:
            current_slide_content = current_slide_data
        
        # Get surrounding slides for context
        context_slides = get_slide_context(current_slide, slides)
        
        # Upload the PDF file to Gemini
        sample_file = client.files.upload(file=PDF_PATH)
        
        # Construct prompt with slide content and question
        prompt = f"""This is a question about slide {current_slide} of the PDF document.

Question: {question}

Current Slide Content:
{current_slide_content}

Surrounding Slides Content:
{", ".join([f"Slide {num}: {content}" for num, content in context_slides.items()])}

Please focus on answering the question based on both the PDF content and the slide summaries provided.
Format your response as valid markdown text."""

        # Call Gemini with both PDF and prompt
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[sample_file, prompt]
        )

        # Get the response text
        response_text = response.text

        # If the response looks like it might be JSON, try to fix it
        if '{' in response_text and '}' in response_text:
            try:
                response_text = fix_json_response(response_text)
            except Exception as e:
                print(f"Failed to fix JSON response: {str(e)}")
                # Continue with original response if fixing fails
        
        return jsonify({
            'success': True,
            'response': response_text
        })
        
    except Exception as e:
        print(f"Error in ask_gemini: {str(e)}")  # Add logging
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/process_pdf', methods=['POST'])
def trigger_processing():
    try:
        def run_async():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(process_pdf())
            loop.close()

        # Run the processing in a background thread
        thread = threading.Thread(target=run_async)
        thread.start()
        
        return jsonify({
            'success': True,
            'message': 'PDF processing started'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
