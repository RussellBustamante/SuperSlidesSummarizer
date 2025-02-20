# SuperSlidesSummarizer

PDF presentation summarizer that uses Google's Gemini AI to analyze and provide explanations for academic slides.

- IMPORTANT NOTE: The application creates cache files to store processed data. If you want to truly reprocess your slides, you must delete the cache.

## Prerequisites

- Python 3.8 or higher
- Your Gemini API key

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/pdfsummarizer.git
cd pdfsummarizer
```

2. Create and activate a virtual environment (recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows, use: venv\Scripts\activate
```

3. Install the required dependencies:
```bash
pip install flask google-generativeai python-dotenv
```

4. Set up your environment variables:
   - Create a `.env` file in the root directory
   - Add your Gemini API key:
```
GEMINI_API_KEY=your_api_key_here
```

## Usage

1. Place your PDF presentation file in the root directory and name it `03-storage1.pdf` (or update the `PDF_PATH` variable in `server.py` to match your filename)

2. Start the server:
```bash
python server.py
```

3. Open your web browser and navigate to:
```
http://localhost:5001 or http://127.0.0.1:5001/ are possible links.
```
- Note: Your link may be different. Check your terminal logs for the exact link.

The application will:
- Process your PDF presentation
- Generate summaries for each slide
- Provide an interactive interface to explore and ask questions about your presentation

## Project Structure

- `server.py`: Main Flask server that handles web requests and API endpoints
- `app.py`: Core logic for PDF processing and Gemini AI integration
- `static/`: Contains JavaScript, CSS, and processed data
- `templates/`: Contains HTML templates
- `.cache/`: Stores processed slide data to avoid reprocessing

## Troubleshooting

1. If you see "API key not found" error:
   - Make sure your `.env` file exists and contains the correct API key
   - Ensure the `.env` file is in the root directory

2. If the PDF isn't loading:
   - Verify the PDF file exists in the correct location
   - Check that the filename matches the `PDF_PATH` in `server.py`

3. For logging and debugging:
   - Check `pdfsummarizer.log` for detailed error messages
   - The server runs in debug mode by default

## Notes

- The application creates cache files to store processed data. If you want to truly reprocess your slides, you must delete the cache.
- Logs are automatically rotated to prevent excessive file sizes
- The server runs on port 5001 by default
