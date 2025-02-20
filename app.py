from google import genai
from google.genai import types
import pathlib
import os
from dotenv import load_dotenv
import asyncio
import json
import re
import logging
import logging.handlers
from datetime import datetime

def setup_logging():
    logger = logging.getLogger('pdfsummarizer')
    logger.setLevel(logging.INFO)
    log_file = 'pdfsummarizer.log'
    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=1024*1024, backupCount=5
    )
    console_handler = logging.StreamHandler()
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger

logger = setup_logging()

def truncate_log(message, max_length=100):
    if len(message) > max_length:
        return message[:max_length-3] + "..."
    return message

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    logger.error("API key not found. Make sure .env file is set correctly.")
    raise ValueError("API key not found. Make sure .env file is set correctly.")

# Configure the client using the previous working method
client = genai.Client(api_key=api_key)

def get_cache_path(pdf_path):
    try:
        pdf_path = pathlib.Path(pdf_path)
        cache_dir = pdf_path.parent / '.cache'
        cache_dir.mkdir(exist_ok=True)
        logger.debug(f"Created cache directory: {cache_dir}")
        return cache_dir / f"{pdf_path.stem}_summary.txt"
    except Exception as e:
        logger.error(f"Failed to create cache path: {truncate_log(str(e))}")
        raise

def read_cache(cache_path):
    try:
        # Convert string to Path if needed
        if isinstance(cache_path, str):
            cache_path = pathlib.Path(cache_path)
            
        if cache_path.exists():
            logger.info(f"Reading cache from: {truncate_log(str(cache_path))}")
            with open(cache_path, 'r', encoding='utf-8') as f:
                return f.read()
    except Exception as e:
        logger.error(f"Cache read error: {truncate_log(str(e))}")
    return None

def write_cache(cache_path, content):
    try:
        # Convert string to Path if needed
        if isinstance(cache_path, str):
            cache_path = pathlib.Path(cache_path)
            
        # Create parent directories if they don't exist
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(cache_path, 'w', encoding='utf-8') as f:
            f.write(content)
        logger.info(f"Cache written to: {truncate_log(str(cache_path))}")
    except Exception as e:
        logger.error(f"Cache write error: {truncate_log(str(e))}")
        raise

def get_initial_summary(file_path):
    try:
        cache_path = get_cache_path(file_path)
        cached_summary = read_cache(cache_path)
        if cached_summary:
            logger.info("Using cached overall summary")
            return cached_summary
        logger.info(f"Uploading file for overall summarization: {truncate_log(str(file_path))}")
        sample_file = client.files.upload(file=file_path)
        logger.info("Requesting overall summary from Gemini...")
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[sample_file, "Please summarize each page of this document."]
        )
        summary_preview = truncate_log(response.text)
        logger.info(f"Overall summary received. Preview: {summary_preview}")
        write_cache(cache_path, response.text)
        return response.text
    except Exception as e:
        logger.error(f"Failed to get overall summary: {truncate_log(str(e))}")
        raise

def get_chunk_summary(file_path):
    try:
        # Check cache first
        base_cache_path = get_cache_path(file_path)
        cache_path = str(base_cache_path).replace('_summary.txt', '_chunks.json')
        cached_content = read_cache(cache_path)
        if cached_content:
            logger.info("Using cached chunk summary")
            try:
                return json.loads(cached_content)
            except json.JSONDecodeError:
                logger.warning("Cached chunk summary is invalid JSON, regenerating...")

        logger.info(f"Uploading file for chunk summarization: {truncate_log(str(file_path))}")
        sample_file = client.files.upload(file=file_path)
        chunk_prompt = '''
        Analyze this document as if you are a computer science professor teaching a database systems course. Group the slides into meaningful chunks based on their content, with special attention to the following:

        1. EVERY slide must be analyzed and included in the output, even if it's a logistics/administrative slide
        2. Group logistics/administrative slides into their own chunk(s)
        3. For slides showing similar diagrams with slight differences, explain what changed and why it's pedagogically important
        4. Pay special attention to slides that build upon each other or show progressive changes

        Required JSON structure (must be valid, no extra text):
        {
            "academic_context": "Brief overview of the lecture's academic content",
            "chunks": [
                {
                    "topic": "Topic name (e.g., 'Core Concepts', 'Progressive Examples', 'Course Logistics')",
                    "pedagogical_goal": "What students should learn from this chunk",
                    "slides": ["Detailed content of each slide"],
                    "slide_numbers": [1, 2, 3],
                    "is_logistics": false
                }
            ]
        }

        Remember: You are a professor explaining these concepts to students. Every slide should be analyzed for its educational value.
        IMPORTANT: Return ONLY valid JSON with no additional text.
        '''
        logger.info("Requesting chunk summary from Gemini...")
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[sample_file, chunk_prompt]
        )
        text = response.text.strip()
        logger.debug(f"Raw JSON response for chunk summarization: {truncate_log(text)}")
        try:
            parsed_json = json.loads(text)
            logger.info("Successfully parsed structured JSON for chunk summarization")
            # Cache the successful response
            write_cache(cache_path, json.dumps(parsed_json, indent=2))
            return parsed_json
        except json.JSONDecodeError as e:
            logger.warning(f"Direct JSON parsing for chunk summary failed: {truncate_log(str(e))}")
            logger.info("Attempting regex extraction for chunk summary...")
            potential_json = re.sub(r'^[^{]*|[^}]*$', '', text)
            try:
                if potential_json:
                    parsed_json = json.loads(potential_json)
                    logger.info("Successfully parsed JSON after cleanup")
                    if "academic_context" in parsed_json and "chunks" in parsed_json:
                        # Cache the cleaned and valid JSON
                        write_cache(cache_path, json.dumps(parsed_json, indent=2))
                        return parsed_json
                logger.warning("Cleaned JSON still invalid or missing required fields")
            except json.JSONDecodeError:
                logger.error("Failed to parse cleaned JSON")
            
            logger.warning("Returning empty structure for chunk summary due to parsing failures")
            return {"academic_context": "", "chunks": []}
    except Exception as e:
        logger.error(f"Failed to get chunk summary: {truncate_log(str(e))}")
        raise

def get_slide_prompt(slide_number, overall_summary, structured_data):
    chunk_context = None 
    for chunk in structured_data.get('chunks', []):
        if slide_number in chunk.get('slide_numbers', []):
            chunk_context = chunk
            break

    prompt = f"""Analyze slide {slide_number} and explain its technical content clearly and thoroughly.

Output Format:
Slide {slide_number}: [Brief Title]

[Direct explanation in clear markdown - DO NOT use code blocks]

Key points to cover:
1. Core technical concepts and their significance
2. Practical implications and real-world applications 
3. Connection to other database concepts
4. Examples that illustrate the concepts

Use markdown for:
- Headers (#)
- Lists (* or -)
- Important terms (**bold**)
- Brief code examples in `backticks` only

Context:
{overall_summary}

Chunk Context:
{chunk_context}
"""
    return prompt

async def process_slide(slide_number, overall_summary, structured_data, slide_texts):
    try:
        prompt = get_slide_prompt(slide_number, overall_summary, structured_data)
        logger.info(f"Requesting unique explanation for Slide {slide_number}...")
        response = await asyncio.to_thread(
            lambda: client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt
            )
        )
        logger.info(f"Successfully generated summary for slide {slide_number}")
        
        text = response.text.strip()
        title_match = re.search(r'^#\s*(.*?)(?=\n|$)', text)
        title = title_match.group(1) if title_match else f"Slide {slide_number}"
        
        return {
            'slide_number': slide_number,
            'title': title,
            'explanation': text
        }
    except Exception as e:
        logger.error(f"Failed to process slide {slide_number}: {truncate_log(str(e))}")
        raise

async def process_all_academic_slides(overall_summary, structured_data):
    try:
        slide_texts_path = pathlib.Path("static/data/slide_texts.json")
        
        # Get all slide numbers from all chunks
        all_slides = set()
        for chunk in structured_data.get('chunks', []):
            for sn in chunk.get('slide_numbers', []):
                all_slides.add(sn)
        
        logger.info(f"Found {len(all_slides)} slides to process")
        
        # Try to load existing slide_texts first
        try:
            with open(slide_texts_path, 'r') as f:
                slide_texts = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            slide_texts = {}
        
        # Initialize any missing slides
        for slide_num in all_slides:
            if str(slide_num) not in slide_texts:
                slide_texts[str(slide_num)] = {
                    "title": "",
                    "summary": ""
                }
            
        # Save initial state
        with open(slide_texts_path, 'w') as f:
            json.dump(slide_texts, f, indent=4)
        
        # Process slides in smaller batches to avoid overwhelming Gemini
        batch_size = 5
        all_slides_list = sorted(list(all_slides))
        successful_slides = 0
        
        for i in range(0, len(all_slides_list), batch_size):
            batch = all_slides_list[i:i + batch_size]
            logger.info(f"Processing batch of slides {batch}")
            
            # Process batch in parallel
            tasks = []
            for sn in batch:
                # Find the chunk this slide belongs to
                chunk_context = None
                for chunk in structured_data.get('chunks', []):
                    if sn in chunk.get('slide_numbers', []):
                        chunk_context = chunk
                        break
                
                task = process_slide(sn, overall_summary, structured_data, slide_texts)
                tasks.append(task)
            
            # Wait for all slides in this batch to complete
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Update slide_texts with results
            for res in batch_results:
                if isinstance(res, Exception):
                    logger.error(f"Failed to process slide: {truncate_log(str(res))}")
                    continue
                    
                sn = res.get('slide_number')
                if sn:
                    if 'title' in res:
                        slide_texts[str(sn)]["title"] = res['title']
                    if 'explanation' in res:
                        slide_texts[str(sn)]["summary"] = res['explanation']
                    successful_slides += 1
                    logger.info(f"Slide {sn} successfully summarized")
            
            # Save after each batch
            try:
                with open(slide_texts_path, 'w') as f:
                    json.dump(slide_texts, f, indent=4)
                logger.info(f"Saved progress after batch ending with slide {batch[-1]}")
            except Exception as e:
                logger.error(f"Failed to save progress: {truncate_log(str(e))}")
        
        logger.info(f"Successfully processed {successful_slides} out of {len(all_slides)} slides")
        return slide_texts, all_slides
    except Exception as e:
        logger.error(f"Failed to process slides: {truncate_log(str(e))}")
        raise

async def main():
    start_time = datetime.now()
    logger.info("===== STARTING PDF SUMMARIZATION =====")
    
    try:
        file_path = pathlib.Path("/Users/anthony/Desktop/2025_cs_projects/pdfsummarizer/03-storage1.pdf")
        logger.info(f"Processing file: {truncate_log(str(file_path))}")
        
        # Get overall summary and chunk data
        overall_future = asyncio.to_thread(get_initial_summary, file_path)
        chunk_future = asyncio.to_thread(get_chunk_summary, file_path)
        overall_summary, structured_data = await asyncio.gather(overall_future, chunk_future)
        
        if not structured_data.get('chunks'):
            logger.warning("No valid academic chunks found. Exiting.")
            return
        
        logger.info("Generating unique explanations for each academic slide...")
        await process_all_academic_slides(overall_summary, structured_data)
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.info(f"===== PROCESS COMPLETE (Duration: {duration:.2f}s) =====")
        
    except Exception as e:
        logger.error(f"Process failed: {truncate_log(str(e))}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
