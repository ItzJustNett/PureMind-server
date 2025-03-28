import json
import os
import requests
import traceback
import dotenv
import logging
import re
import datetime
from typing import Dict, List, Any, Optional, Tuple

# Import the new transcript downloader
from transcript_downloader import get_transcript, get_video_metadata

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
dotenv.load_dotenv()

# Get OpenRouter API key from environment variables
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
if not OPENROUTER_API_KEY:
    logger.warning("OPENROUTER_API_KEY not found in .env file")

# OpenRouter API configuration
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = "moonshotai/moonlight-16b-a3b-instruct:free"  # Updated model
OPENROUTER_HEADERS = {
    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
    "Content-Type": "application/json"
}

# Lessons data global variable
lessons_data = {}

def load_lessons_data(file_path: str = 'lessons.json') -> Dict:
    """Load lessons data from the JSON file"""
    global lessons_data
    try:
        # Read the lessons.json file
        with open(file_path, 'r', encoding='utf-8') as file:
            lessons_data = json.load(file)
        logger.info(f"Loaded {len(lessons_data)} lessons")
        return lessons_data
    except Exception as e:
        logger.error(f"Error loading lessons data: {e}")
        return {}

def search_lessons(query: str) -> List[Dict]:
    """Search lessons by title or ID"""
    if not query:
        return []
    
    query = query.lower()
    results = [lesson for lesson in lessons_data.values() 
               if query in lesson.get('title', '').lower() or 
                  query in lesson.get('id', '').lower()]
    
    return results

def get_lesson(lesson_id: str) -> Optional[Dict]:
    """Get a specific lesson by ID"""
    return lessons_data.get(lesson_id)

def get_youtube_link(lesson_id: str) -> Optional[Dict]:
    """Get the YouTube link for a specific lesson"""
    lesson = lessons_data.get(lesson_id)
    
    if not lesson or not lesson.get('youtube_link'):
        return None
    
    return {
        "id": lesson.get('id'),
        "title": lesson.get('title'),
        "youtube_link": lesson.get('youtube_link')
    }

def list_lessons() -> List[Dict]:
    """List all lessons (simplified)"""
    simplified_list = [{
        "id": lesson.get('id'),
        "title": lesson.get('title'),
        "course_id": lesson.get('course_id')
    } for lesson in lessons_data.values()]
    
    return simplified_list

def generate_conspect(lesson_id: str) -> Tuple[Dict, int]:
    """Generate a lesson summary using OpenRouter API with Moonlight model"""
    try:
        lesson = lessons_data.get(lesson_id)
        
        if not lesson:
            return {"error": "Lesson not found"}, 404
        
        if not OPENROUTER_API_KEY:
            return {"error": "OpenRouter API key not configured in .env file"}, 500
        
        # Get lesson title and YouTube link
        title = lesson.get('title', '')
        youtube_link = lesson.get('youtube_link', '')
        course_id = lesson.get('course_id', '')
        
        if not youtube_link:
            return {"error": "No YouTube link available for this lesson"}, 404
        
        # Download transcript from YouTube
        logger.info(f"Downloading transcript for lesson: {title}, URL: {youtube_link}")
        transcript, transcript_error = get_transcript(youtube_link)
        
        if transcript_error:
            logger.error(f"Error downloading transcript: {transcript_error}")
            return {
                "error": "Failed to download transcript", 
                "details": transcript_error,
                "message": "Please use yt_dlp to download the webpage and transcript manually"
            }, 500
        
        if not transcript:
            return {
                "error": "No transcript available", 
                "message": "The video doesn't have subtitles or a transcript"
            }, 404
        
        # Get video metadata for additional context
        metadata, metadata_error = get_video_metadata(youtube_link)
        metadata_str = ""
        if metadata and not metadata_error:
            metadata_str = f"""
Video Title: {metadata.get('title', 'Unknown')}
Channel: {metadata.get('channel', 'Unknown')}
Duration: {metadata.get('duration', 0)} seconds
            """
        
        # Prepare the prompt for the AI
        prompt = f"""
        Please create a comprehensive conspect (summary) for a lesson titled "{title}".
        This lesson is part of the course "{course_id}" and has this YouTube video: {youtube_link}.
        
        Here is the metadata for the video:
        {metadata_str}
        
        Here is the transcript of the video:
        {transcript[:4000]}  # Limit transcript length to avoid token limits
        
        The summary should:
        1. Cover the main topics and concepts from the lesson
        2. Be well-structured with clear headings and bullet points
        3. Include key definitions and important facts
        4. Be written in Ukrainian language
        
        Format the response as markdown text.
        """
        
        logger.info(f"Sending request to OpenRouter for lesson: {title}")
        
        # Make request to OpenRouter API
        response = requests.post(
            OPENROUTER_API_URL,
            headers=OPENROUTER_HEADERS,
            json={
                "model": OPENROUTER_MODEL,
                "messages": [
                    {"role": "system", "content": "You are a helpful educational assistant that creates lesson summaries in Ukrainian."},
                    {"role": "user", "content": prompt}
                ]
            },
            timeout=30  # Set timeout to 30 seconds
        )
        
        logger.info(f"OpenRouter response status: {response.status_code}")
        
        if response.status_code != 200:
            logger.error(f"OpenRouter API error: {response.text}")
            return {
                "error": f"OpenRouter API error: {response.status_code}",
                "details": response.text
            }, 500
        
        result = response.json()
        logger.info("OpenRouter response received")
        
        conspect_text = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        
        if not conspect_text:
            logger.error("Failed to extract content from OpenRouter response")
            return {
                "error": "Failed to generate conspect, content was empty", 
                "response": result
            }, 500
        
        # If we got here, everything is successful
        return {
            "lesson_id": lesson_id,
            "title": title,
            "course_id": course_id,
            "conspect": conspect_text
        }, 200
        
    except Exception as e:
        # Print full exception details to console
        logger.error(f"Error in generate_conspect: {str(e)}")
        logger.error(traceback.format_exc())
        
        # Return detailed error information
        return {
            "error": f"Error generating conspect: {str(e)}",
            "traceback": traceback.format_exc()
        }, 500

def generate_test(course_id: str) -> Tuple[Dict, int]:
    """Generate a course test using OpenRouter API with Moonlight model"""
    try:
        # Check if course exists
        course_lessons = [lesson for lesson in lessons_data.values() if lesson.get('course_id') == course_id]
        
        if not course_lessons:
            return {"error": f"No lessons found for course: {course_id}"}, 404
        
        if not OPENROUTER_API_KEY:
            return {"error": "OpenRouter API key not configured in .env file"}, 500
        
        # Get course lesson titles to provide context
        lesson_titles = [lesson.get('title', '') for lesson in course_lessons]
        
        # Collect transcripts from up to 3 lessons in the course
        transcripts = []
        for lesson in course_lessons[:3]:  # Limit to first 3 lessons to avoid token limits
            youtube_link = lesson.get('youtube_link')
            if youtube_link:
                transcript, error = get_transcript(youtube_link)
                if transcript and not error:
                    # Truncate transcript to avoid token limits
                    truncated_transcript = transcript[:2000] + "..." if len(transcript) > 2000 else transcript
                    transcripts.append({
                        "title": lesson.get('title', ''),
                        "transcript": truncated_transcript
                    })
        
        # Prepare content based on transcripts
        content_section = ""
        if transcripts:
            content_section = "Here are transcripts from some lessons in the course:\n\n"
            for idx, item in enumerate(transcripts):
                content_section += f"Lesson {idx+1}: {item['title']}\n{item['transcript']}\n\n"
        else:
            content_section = "No transcripts available. Please generate questions based on the lesson titles."
        
        # Prepare the prompt for the AI
        prompt = f"""
        Create a test with exactly 15 questions about the course "{course_id}".
        The course includes these lessons: {", ".join(lesson_titles)}
        
        {content_section}
        
        For each question:
        1. Provide a question text
        2. Provide exactly 4 answer options (A, B, C, D)
        3. Indicate which answer is correct
        4. Write the test in Ukrainian language
        
        Return the test in a structured JSON format that looks exactly like this:
        {{
          "course_id": "{course_id}",
          "questions": [
            {{
              "question": "Question text here",
              "options": [
                "Answer option A",
                "Answer option B", 
                "Answer option C",
                "Answer option D"
              ],
              "correct_answer": 0  // Index of correct answer (0-3)
            }},
            // More questions...
          ]
        }}
        
        Make sure the response is valid JSON that can be parsed.
        """
        
        logger.info(f"Sending request to OpenRouter for test generation for course: {course_id}")
        
        # Make request to OpenRouter API
        response = requests.post(
            OPENROUTER_API_URL,
            headers=OPENROUTER_HEADERS,
            json={
                "model": OPENROUTER_MODEL,
                "messages": [
                    {"role": "system", "content": "You are a helpful educational assistant that creates tests in Ukrainian."},
                    {"role": "user", "content": prompt}
                ]
            },
            timeout=60  # Longer timeout for test generation
        )
        
        logger.info(f"OpenRouter response status: {response.status_code}")
        
        if response.status_code != 200:
            logger.error(f"OpenRouter API error: {response.text}")
            return {
                "error": f"OpenRouter API error: {response.status_code}",
                "details": response.text
            }, 500
        
        result = response.json()
        logger.info("OpenRouter response received for test generation")
        
        test_content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        
        if not test_content:
            logger.error("Failed to extract content from OpenRouter response")
            return {
                "error": "Failed to generate test, content was empty", 
                "response": result
            }, 500
        
        # Try to extract JSON from the response
        # Sometimes the AI might wrap the JSON in markdown code blocks
        try:
            # Try direct parsing first
            test_json = json.loads(test_content)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON directly: {e}")
            # Try to extract JSON if it's wrapped in code blocks
            json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', test_content)
            if json_match:
                try:
                    test_json = json.loads(json_match.group(1))
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse extracted JSON: {e}")
                    return {
                        "error": "Failed to parse test JSON", 
                        "raw_content": test_content,
                        "parsing_error": str(e)
                    }, 500
            else:
                return {
                    "error": "Failed to parse test JSON - no JSON structure found", 
                    "raw_content": test_content
                }, 500
        
        # Validate the structure
        if not isinstance(test_json, dict) or "questions" not in test_json:
            logger.error(f"Invalid test format: {json.dumps(test_json, indent=2)}")
            return {
                "error": "Invalid test format", 
                "generated_content": test_json
            }, 500
        
        # Add timestamp and course data
        test_json["timestamp"] = str(datetime.datetime.now())
        test_json["course_id"] = course_id
        
        return test_json, 200
        
    except Exception as e:
        # Print full exception details to console
        logger.error(f"Error in generate_test: {str(e)}")
        logger.error(traceback.format_exc())
        
        # Return detailed error information
        return {
            "error": f"Error generating test: {str(e)}",
            "traceback": traceback.format_exc()
        }, 500

def generate_lesson_test(lesson_id: str) -> Tuple[Dict, int]:
    """Generate a test for a specific lesson using OpenRouter API"""
    try:
        lesson = lessons_data.get(lesson_id)
        
        if not lesson:
            return {"error": "Lesson not found"}, 404
        
        if not OPENROUTER_API_KEY:
            return {"error": "OpenRouter API key not configured in .env file"}, 500
        
        # Get lesson title and YouTube link
        title = lesson.get('title', '')
        youtube_link = lesson.get('youtube_link', '')
        course_id = lesson.get('course_id', '')
        
        if not youtube_link:
            return {"error": "No YouTube link available for this lesson"}, 404
        
        # Download transcript from YouTube
        logger.info(f"Downloading transcript for lesson: {title}, URL: {youtube_link}")
        transcript, transcript_error = get_transcript(youtube_link)
        
        if transcript_error:
            logger.error(f"Error downloading transcript: {transcript_error}")
            return {
                "error": "Failed to download transcript", 
                "details": transcript_error,
                "message": "Please use yt_dlp to download the webpage and transcript manually"
            }, 500
        
        if not transcript:
            return {
                "error": "No transcript available", 
                "message": "The video doesn't have subtitles or a transcript"
            }, 404
        
        # Prepare the prompt for the AI
        prompt = f"""
        Create a test with 10 questions about the lesson titled "{title}".
        
        Here is the transcript of the video:
        {transcript[:4000]}  # Limit transcript length to avoid token limits
        
        For each question:
        1. Provide a question text
        2. Provide exactly 4 answer options (A, B, C, D)
        3. Indicate which answer is correct
        4. Write the test in Ukrainian language
        
        Return the test in a structured JSON format that looks exactly like this:
        {{
          "lesson_id": "{lesson_id}",
          "title": "{title}",
          "questions": [
            {{
              "question": "Question text here",
              "options": [
                "Answer option A",
                "Answer option B", 
                "Answer option C",
                "Answer option D"
              ],
              "correct_answer": 0  // Index of correct answer (0-3)
            }},
            // More questions...
          ]
        }}
        
        Make sure the response is valid JSON that can be parsed.
        """
        
        logger.info(f"Sending request to OpenRouter for test generation for lesson: {title}")
        
        # Make request to OpenRouter API
        response = requests.post(
            OPENROUTER_API_URL,
            headers=OPENROUTER_HEADERS,
            json={
                "model": OPENROUTER_MODEL,
                "messages": [
                    {"role": "system", "content": "You are a helpful educational assistant that creates tests in Ukrainian."},
                    {"role": "user", "content": prompt}
                ]
            },
            timeout=45  # Timeout for test generation
        )
        
        logger.info(f"OpenRouter response status: {response.status_code}")
        
        if response.status_code != 200:
            logger.error(f"OpenRouter API error: {response.text}")
            return {
                "error": f"OpenRouter API error: {response.status_code}",
                "details": response.text
            }, 500
        
        result = response.json()
        logger.info("OpenRouter response received for lesson test generation")
        
        test_content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        
        if not test_content:
            logger.error("Failed to extract content from OpenRouter response")
            return {
                "error": "Failed to generate test, content was empty", 
                "response": result
            }, 500
        
        # Try to extract JSON from the response (similar to generate_test)
        try:
            # Try direct parsing first
            test_json = json.loads(test_content)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON directly: {e}")
            # Try to extract JSON if it's wrapped in code blocks
            json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', test_content)
            if json_match:
                try:
                    test_json = json.loads(json_match.group(1))
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse extracted JSON: {e}")
                    return {
                        "error": "Failed to parse test JSON", 
                        "raw_content": test_content,
                        "parsing_error": str(e)
                    }, 500
            else:
                return {
                    "error": "Failed to parse test JSON - no JSON structure found", 
                    "raw_content": test_content
                }, 500
        
        # Validate the structure
        if not isinstance(test_json, dict) or "questions" not in test_json:
            logger.error(f"Invalid test format: {json.dumps(test_json, indent=2)}")
            return {
                "error": "Invalid test format", 
                "generated_content": test_json
            }, 500
        
        # Add timestamp
        test_json["timestamp"] = str(datetime.datetime.now())
        
        return test_json, 200
        
    except Exception as e:
        # Print full exception details to console
        logger.error(f"Error in generate_lesson_test: {str(e)}")
        logger.error(traceback.format_exc())
        
        # Return detailed error information
        return {
            "error": f"Error generating lesson test: {str(e)}",
            "traceback": traceback.format_exc()
        }, 500

def test_openrouter_connection() -> Tuple[Dict, int]:
    """Test the connection to OpenRouter API"""
    try:
        if not OPENROUTER_API_KEY:
            return {
                "success": False,
                "error": "OpenRouter API key not configured in .env file"
            }, 400
        
        # Make a simple request to the OpenRouter API
        response = requests.post(
            OPENROUTER_API_URL,
            headers=OPENROUTER_HEADERS,
            json={
                "model": OPENROUTER_MODEL,
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": "Say hello!"}
                ]
            },
            timeout=10
        )
        
        if response.status_code != 200:
            return {
                "success": False,
                "error": f"OpenRouter API error: {response.status_code}",
                "details": response.text
            }, response.status_code
        
        return {
            "success": True,
            "message": "OpenRouter connection is working"
        }, 200
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Error testing OpenRouter connection: {str(e)}"
        }, 500

# Initialize data when the module is imported
load_lessons_data()