import requests
from bs4 import BeautifulSoup
import json
import os
import time
import re

# --- CONFIGURATION ---
BASE_URL = "https://www.churchofjesuschrist.org/study/scriptures/bofm/{}/{}?lang={}"

BOOKS = [
    {"abbr": "1-ne", "chapters": 22},
    {"abbr": "2-ne", "chapters": 33},
    {"abbr": "jacob", "chapters": 7},
    {"abbr": "enos", "chapters": 1},
    {"abbr": "jarom", "chapters": 1},
    {"abbr": "omni", "chapters": 1},
    {"abbr": "w-of-m", "chapters": 1},
    {"abbr": "mosiah", "chapters": 29},
    {"abbr": "alma", "chapters": 63},
    {"abbr": "hel", "chapters": 16},
    {"abbr": "3-ne", "chapters": 30},
    {"abbr": "4-ne", "chapters": 1},
    {"abbr": "morm", "chapters": 9},
    {"abbr": "ether", "chapters": 15},
    {"abbr": "moro", "chapters": 10}
]

def get_chapter_prefix(lang_code):
    """
    Fetches 1 Nephi 1 to find the localized word for 'Chapter' (e.g., 'Capítulo', 'Kapitel').
    """
    url = BASE_URL.format("1-ne", "1", lang_code)
    headers = {'User-Agent': 'Mozilla/5.0'}
    prefix = "Chapter" # Fallback default

    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            title_number_tag = soup.find('p', class_='title-number')
            
            if title_number_tag:
                text = title_number_tag.get_text().strip()
                # Remove the number '1' from the string to get just the word
                clean_text = re.sub(r'\d+', '', text).strip()
                if clean_text:
                    prefix = clean_text
    except Exception as e:
        print(f"Error fetching chapter prefix for {lang_code}: {e}")
    
    return prefix

def get_book_name(book_abbr, chapter_number, lang_code):
    url = BASE_URL.format(book_abbr, chapter_number, lang_code)
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            h1_tag = soup.find('h1', id='title1')
            if h1_tag:
                dominant_span = h1_tag.find('span', class_='dominant')
                if dominant_span:
                    return dominant_span.get_text().strip()
                return h1_tag.get_text().strip()
    except Exception as e:
        print(f"Error fetching book name for {book_abbr}: {e}")
    return book_abbr

def get_chapter_data(lang_code, book_abbr, chapter_number):
    url = BASE_URL.format(book_abbr, chapter_number, lang_code)
    headers = {'User-Agent': 'Mozilla/5.0'}
    chapter_verses = {}
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')

            # --- 1. Fetch Introduction ---
            intro_paragraphs = soup.find_all('p', class_='intro')
            if intro_paragraphs:
                intro_text = "\n\n".join([p.get_text().strip() for p in intro_paragraphs])
                if intro_text:
                    chapter_verses['intro'] = intro_text

            # --- 2. Fetch Verses ---
            verses = soup.find_all('p', class_='verse')

            for verse in verses:
                verse_number_tag = verse.find('span', class_='verse-number')
                verse_number = verse_number_tag.text.strip() if verse_number_tag else "0"
                
                verse_text = ''.join([
                    str(element) if isinstance(element, str) else element.get_text()
                    for element in verse.contents
                ]).strip()

                if verse_text.startswith(verse_number):
                    verse_text = verse_text[len(verse_number):].strip()
                
                chapter_verses[verse_number] = verse_text
    except Exception as e:
        print(f"Error fetching chapter {chapter_number} of {book_abbr}: {e}")

    return chapter_verses

def process_language(lang_obj, output_dir):
    lang_code = lang_obj.get('code')
    lang_name = lang_obj.get('language name', 'Unknown')
    
    print(f"\n--- Starting: {lang_name} ({lang_code}) ---")
    
    # 1. Get the localized "Chapter" word
    chapter_prefix = get_chapter_prefix(lang_code)
    print(f"   Localized Chapter Prefix: '{chapter_prefix}'")

    filename = f'{lang_code}.json'
    full_path = os.path.join(output_dir, filename)
    
    bofm_data = {}

    for book in BOOKS:
        slug = book['abbr'] # This is the standard key (e.g., "1-ne")
        
        # Get Book Name (localized)
        localized_book_name = get_book_name(slug, 1, lang_code)
        
        print(f"  Processing {slug} -> {localized_book_name}...")
        
        # Initialize the book structure with metadata and a content holder
        bofm_data[slug] = {
            "meta": {
                "slug": slug,
                "name": localized_book_name,
                "chapterWord": chapter_prefix
            },
            "chapters": {}
        }
        
        for chapter in range(1, book['chapters'] + 1):
            verses_dict = get_chapter_data(lang_code, slug, chapter)
            
            # We use the clean number "1" as the key.
            # Your app can reconstruct "Chapter 1" using the "chapterWord" from meta.
            bofm_data[slug]["chapters"][str(chapter)] = verses_dict
            
    # Save to JSON file
    with open(full_path, 'w', encoding='utf-8') as f:
        json.dump(bofm_data, f, ensure_ascii=False, indent=4)

    print(f"Saved: {full_path}")

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    
    languages_file_path = os.path.join(project_root, 'languages.json')
    output_dir = os.path.join(project_root, 'all_books')

    os.makedirs(output_dir, exist_ok=True)

    if not os.path.exists(languages_file_path):
        print(f"Error: Could not find languages file at {languages_file_path}")
        return

    with open(languages_file_path, 'r', encoding='utf-8') as f:
        languages_list = json.load(f)

    print(f"Found {len(languages_list)} languages to process.")

    for lang in languages_list:
        try:
            process_language(lang, output_dir)
        except Exception as e:
            print(f"CRITICAL ERROR processing language {lang.get('code')}: {e}")

if __name__ == "__main__":
    main()