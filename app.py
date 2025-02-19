from google import genai
from google.genai import types
import pathlib
import os
from dotenv import load_dotenv
import asyncio
import json
import re

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError("API key not found. Make sure .env file is set correctly.")

client = genai.Client(api_key=api_key)

def get_cache_path(pdf_path):
    """Generate a cache file path for a given PDF."""
    pdf_path = pathlib.Path(pdf_path)
    cache_dir = pdf_path.parent / '.cache'
    cache_dir.mkdir(exist_ok=True)
    return cache_dir / f"{pdf_path.stem}_summary.txt"

def read_cache(cache_path):
    """Read summary from cache if it exists."""
    try:
        if cache_path.exists():
            print(f"Cache found at: {cache_path}")
            with open(cache_path, 'r', encoding='utf-8') as f:
                return f.read()
    except Exception as e:
        print(f"Error reading cache: {e}")
    return None

def write_cache(cache_path, content):
    """Write summary to cache."""
    try:
        with open(cache_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Cache written to: {cache_path}")
    except Exception as e:
        print(f"Error writing cache: {e}")

def get_initial_summary(file_path):
    cache_path = get_cache_path(file_path)
    cached_summary = read_cache(cache_path)
    
    if cached_summary:
        print("Using cached summary")
        return cached_summary
        
    print(f"No cache found. Uploading file for summarization: {file_path}")
    sample_file = client.files.upload(file=file_path)
    print("Requesting initial summary from Gemini...")
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=[sample_file, "Please summarize each page of this document."]
    )
    print("Summary received. First 500 characters:")
    print(response.text[:500])
    
    # Cache the response
    write_cache(cache_path, response.text)
    return response.text

def parse_chunks(summary):
    print("Parsing summary into structured JSON format...")
    format_prompt = f"""
    Based on the following summary, create a JSON structure:
    {{
        "academic_context": "brief overall academic context",
        "chunks": [
            {{
                "topic": "topic name",
                "slides": ["slide content 1", "slide content 2"],
                "slide_numbers": [1, 2]
            }}
        ]
    }}
    Rules:
    1. Only include academic content, no logistics.
    2. Ensure valid JSON format.
    Here's the summary to process:
    {summary}
    """
    print("Requesting structured JSON from Gemini...")
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=format_prompt
    )
    text = response.text.strip()
    print("Raw JSON response (truncated):")
    print(text[:500])
    try:
        parsed_json = json.loads(text)
        print("Successfully parsed structured JSON.")
        return parsed_json
    except json.JSONDecodeError:
        print("Direct JSON parsing failed. Attempting regex extraction...")
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            extracted_json = match.group(0)
            try:
                parsed_json = json.loads(extracted_json)
                print("Successfully parsed JSON from regex extraction.")
                return parsed_json
            except json.JSONDecodeError:
                print("Regex extracted JSON is still invalid.")
        print("Returning empty structure.")
        return {"academic_context": "", "chunks": []}

async def process_chunk(chunk, academic_context):
    print(f"Processing chunk: {chunk['topic']} (Slides: {chunk['slide_numbers']})")
    prompt = f"""
    Context: {academic_context}
    
    For these slides about {chunk['topic']}:
    {chunk['slides']}
    
    Provide an in-depth explanation of this topic.
    """
    print(f"Requesting explanation from Gemini for topic: {chunk['topic']}")
    response = await asyncio.to_thread(
        lambda: client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt
        )
    )
    print(f"Explanation received for topic: {chunk['topic']}. First 500 characters:")
    print(response.text[:500])
    return {
        'topic': chunk['topic'],
        'slide_numbers': chunk['slide_numbers'],
        'explanation': response.text
    }

async def process_all_chunks(structured_data):
    print("Processing all chunks asynchronously...")
    tasks = []
    for chunk in structured_data['chunks']:
        print(f"Scheduling processing for chunk: {chunk['topic']}")
        task = process_chunk(chunk, structured_data['academic_context'])
        tasks.append(task)
    print("Starting parallel execution of all chunks...")
    results = await asyncio.gather(*tasks)
    print("All chunks processed. Sorting results by slide number...")
    sorted_results = sorted(results, key=lambda x: x['slide_numbers'][0])
    print("Processing complete. Returning sorted results.")
    return sorted_results

async def main():
    file_path = pathlib.Path("/Users/anthony/Desktop/2025_cs_projects/pdfsummarizer/03-storage1.pdf")
    print("\n===== STARTING PDF SUMMARIZATION =====\n")
    print("Step 1: Extracting initial summary...")
    initial_summary = get_initial_summary(file_path)
    print("\nStep 2: Parsing summary into structured chunks...")
    structured_data = parse_chunks(initial_summary)
    if not structured_data['chunks']:
        print("No valid chunks found. Exiting.")
        return
    print("\nStep 3: Generating explanations for each topic...")
    results = await process_all_chunks(structured_data)
    print("\n===== FINAL RESULTS =====\n")
    for result in results:
        print(f"\n{'='*50}")
        print(f"Topic: {result['topic']}")
        print(f"Slides: {result['slide_numbers']}")
        print(f"{'='*50}")
        print(result['explanation'][:1000])
    print("\n===== PROCESS COMPLETE =====\n")

if __name__ == "__main__":
    asyncio.run(main())
