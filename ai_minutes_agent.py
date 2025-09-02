#!/usr/bin/env python3
"""
AI Minutes Agent - Public Comment Extraction System

This agent processes committee meeting minutes stored as PDF files and extracts
public comments from the "Open Forum" sections.

Author: AI Assistant
Date: 2025-06-26
"""

import os
import re
import sys
import csv
import argparse
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import fitz  # PyMuPDF


class AIMinutesAgent:
    """
    AI agent for processing committee meeting minutes and extracting public comments.
    """
    
    def __init__(self, debug_mode: bool = False):
        """
        Initialize the AI Minutes Agent.
        
        Args:
            debug_mode (bool): Enable debug output for detailed processing info
        """
        self.debug_mode = debug_mode
        self.skipped_files = []
        self.processing_stats = {
            'total_files': 0,
            'processed_files': 0,
            'skipped_files': 0,
            'total_comments': 0
        }
    
    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """
        Extract all text from a PDF file.
        
        Args:
            pdf_path (str): Path to the PDF file
            
        Returns:
            str: Extracted text content
        """
        try:
            doc = fitz.open(pdf_path)
            full_text = ""
            
            for page_num, page in enumerate(doc):
                page_text = page.get_text()
                full_text += page_text
                
                if self.debug_mode:
                    print(f"  Page {page_num + 1}: {len(page_text)} characters")
            
            doc.close()
            return full_text
            
        except Exception as e:
            print(f"Error reading PDF {pdf_path}: {e}")
            return ""
    
    def extract_open_forum_section(self, text: str) -> Optional[str]:
        """
        Extract the Open Forum section from the meeting minutes text.
        
        Args:
            text (str): Full text content of the minutes
            
        Returns:
            Optional[str]: Open Forum section text, or None if not found
        """
        # Pattern to match Open Forum section - including variations and encoding issues
        patterns = [
            # Standard patterns
            r"V\.\s*Open Forum(.*?)(?=VI\.|Discussion Item|VII\.|Action Items|Motion|Adjournment|\Z)",
            r"5\.\s*Open Forum(.*?)(?=6\.|Discussion Item|7\.|Action Items|Motion|Adjournment|\Z)",
            r"Open Forum(.*?)(?=Discussion Item|Action Items|Motion|Adjournment|Next Meeting|\Z)",
            
            # Patterns with encoding variations (like OSHQ FRUXP)
            r"V\.\s*[A-Z]{4}\s+[A-Z]{5}(.*?)(?=VI\.|Discussion Item|VII\.|Action Items|Motion|Adjournment|\Z)",
            r"5\.\s*[A-Z]{4}\s+[A-Z]{5}(.*?)(?=6\.|Discussion Item|7\.|Action Items|Motion|Adjournment|\Z)",
            r"9\.\s*[A-Z]{4}\s+[A-Z]{5}(.*?)(?=VI\.|Discussion Item|VII\.|Action Items|Motion|Adjournment|9I\.|10\.|AQQRXQFHPHQWV|AGMRXUQPHQW|\Z)",
            
            # Specific pattern for the garbled text we found
            r"9\.\s*OSHQ\s+FRUXP(.*?)(?=9I\.|VI\.|Discussion Item|VII\.|Action Items|Motion|Adjournment|AQQRXQFHPHQWV|AGMRXUQPHQW|\Z)",
            
            # More flexible patterns
            r"[IV]*\.\s*[Oo]pen\s+[Ff]orum(.*?)(?=[IV]*\.|Discussion|Action|Motion|Adjournment|Next Meeting|\Z)",
            r"\d+\.\s*[Oo]pen\s+[Ff]orum(.*?)(?=\d+\.|Discussion|Action|Motion|Adjournment|Next Meeting|\Z)"
        ]
        
        for i, pattern in enumerate(patterns):
            match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
            if match:
                open_forum_text = match.group(1).strip()
                
                if self.debug_mode:
                    print(f"  Found Open Forum section using pattern {i+1} ({len(open_forum_text)} characters)")
                    print(f"  Preview: {open_forum_text[:200]}...")
                
                return open_forum_text
        
        if self.debug_mode:
            print("  No Open Forum section found")
        
        return None
    
    def has_no_comments(self, text: str) -> bool:
        """
        Check if the Open Forum section explicitly states no comments.
        
        Args:
            text (str): Open Forum section text
            
        Returns:
            bool: True if section indicates no comments
        """
        no_comment_patterns = [
            r"\b(no open forum|no comments?|none|n/?a|not applicable)\b",
            r"\b(no public comment|no discussion|no speakers?)\b",
            r"\b(no one spoke|no attendees|no participants)\b",
            r"^\s*(none|n/?a)\s*\.?\s*$"
        ]
        
        for pattern in no_comment_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                if self.debug_mode:
                    print(f"  Found 'no comments' indicator: {pattern}")
                return True
        
        return False
    
    def count_public_comments(self, open_forum_text: str) -> int:
        """
        Count the number of distinct public comments in the Open Forum section.
        
        Args:
            open_forum_text (str): Text from the Open Forum section
            
        Returns:
            int: Number of public comments (paragraphs)
        """
        if not open_forum_text or self.has_no_comments(open_forum_text):
            return 0
        
        # Clean the text
        cleaned_text = re.sub(r'\s+', ' ', open_forum_text.strip())
        
        # Check if the section only contains administrative/document metadata
        if self.is_only_admin_content(open_forum_text):
            if self.debug_mode:
                print("  Open Forum section contains only administrative content (no public comments)")
            return 0
        
        # Split into paragraphs (separated by double newlines or similar)
        paragraphs = re.split(r'\n\s*\n|\r\n\s*\r\n', open_forum_text)
        
        # Filter out empty or very short paragraphs and administrative content
        valid_paragraphs = []
        for para in paragraphs:
            para = para.strip()
            # Consider valid if it has substantial content and isn't administrative
            if (len(para) > 20 and 
                not re.match(r'^\s*(page \d+|continued|end)\s*$', para, re.IGNORECASE) and
                not self.is_admin_paragraph(para)):
                
                # Check for clear topic changes within a paragraph
                # Look for patterns like "Topic ended. [Person] asked/stated..."
                topic_parts = self.split_by_clear_boundaries(para)
                valid_paragraphs.extend(topic_parts)
        
        comment_count = len(valid_paragraphs)
        
        if self.debug_mode:
            print(f"  Found {len(paragraphs)} total paragraphs, {comment_count} valid comments")
            for i, para in enumerate(valid_paragraphs[:3]):  # Show first 3
                print(f"    Comment {i+1}: {para[:100]}...")
        
        return comment_count
    
    def split_by_clear_boundaries(self, paragraph: str) -> List[str]:
        """
        Split a paragraph only at very clear topic boundaries where different people speak.
        
        Args:
            paragraph (str): A paragraph that might contain multiple distinct speaker comments
            
        Returns:
            List[str]: List of individual comments
        """
        # Look for very clear speaker changes - sentences that end + person name + action verb
        # This is more conservative than the previous approach
        
        # Pattern: Sentence ending + specific transition + Person + asked/stated/etc
        # Example: "...were listed.\nExternal Affairs Committee meeting times were asked by..."
        pattern = r'(?<=\.)\s*\n(?=[A-Z][a-zA-Z\s,&]+ (meeting times? were asked by|was asked by|asked by|stated by))'
        
        # Also look for clear "Per [Person]" statements that start new topics
        pattern2 = r'(?<=\.)\s*\n(?=Per [A-Z][a-zA-Z\s,]+,)'
        
        # Find split points
        split_points = []
        for pat in [pattern, pattern2]:
            matches = list(re.finditer(pat, paragraph))
            for match in matches:
                split_points.append(match.end() - 1)  # Position just before the capital letter
        
        if not split_points:
            # No clear boundaries found, return as single comment
            return [paragraph.strip()] if paragraph.strip() else []
        
        # Split at the identified points
        split_points = sorted(list(set(split_points)))
        comments = []
        start = 0
        
        for boundary in split_points:
            if start < boundary:
                comment = paragraph[start:boundary].strip()
                if len(comment) > 30:  # Only include substantial comments
                    comments.append(comment)
            start = boundary
        
        # Add the final part
        if start < len(paragraph):
            final_comment = paragraph[start:].strip()
            if len(final_comment) > 30:
                comments.append(final_comment)
        
        # If we couldn't create meaningful splits, return the original
        if not comments:
            return [paragraph.strip()] if paragraph.strip() else []
        
        return comments
    
    def split_by_speakers(self, paragraph: str) -> List[str]:
        """
        Split a paragraph into multiple comments if it contains multiple speakers.
        
        Args:
            paragraph (str): A paragraph that might contain multiple speaker comments
            
        Returns:
            List[str]: List of individual comments
        """
        # Patterns that indicate a new speaker or comment
        # Look for patterns like "X was asked by [Name]" or "[Name] stated/asked/etc"
        speaker_patterns = [
            r'(?:^|\.\s+)([A-Z][a-zA-Z\s&,]+(?:asked|stated|mentioned|said|commented|noted|expressed|inquired|requested)\s+by\s+[A-Z][a-zA-Z\s,]+)',
            r'(?:^|\.\s+)([A-Z][a-zA-Z\s&,]+\s+(?:was|were)\s+asked\s+by\s+[A-Z][a-zA-Z\s,]+)',
            r'(?:^|\.\s+)(Per\s+[A-Z][a-zA-Z\s,]+)',
        ]
        
        # Find all potential split points
        split_points = []
        
        for pattern in speaker_patterns:
            matches = list(re.finditer(pattern, paragraph))
            for match in matches:
                start_pos = match.start()
                # Don't split at the very beginning unless it starts with a sentence
                if start_pos > 10 or paragraph[:start_pos].strip().endswith('.'):
                    split_points.append(start_pos)
        
        # Remove duplicates and sort
        split_points = sorted(list(set(split_points)))
        
        if not split_points:
            # No clear speaker boundaries found, return as single comment
            return [paragraph.strip()] if paragraph.strip() else []
        
        # Split the paragraph at the identified points
        comments = []
        start = 0
        
        for split_point in split_points:
            if start < split_point:
                comment = paragraph[start:split_point].strip()
                # Clean up leading punctuation and whitespace
                comment = re.sub(r'^[.\s]+', '', comment).strip()
                if len(comment) > 30:  # Only include substantial comments
                    comments.append(comment)
            start = split_point
        
        # Add the final part
        if start < len(paragraph):
            final_comment = paragraph[start:].strip()
            # Clean up leading punctuation and whitespace
            final_comment = re.sub(r'^[.\s]+', '', final_comment).strip()
            if len(final_comment) > 30:
                comments.append(final_comment)
        
        # If we couldn't identify meaningful splits, return the original
        if not comments:
            return [paragraph.strip()] if paragraph.strip() else []
        
        return comments
    
    def is_only_admin_content(self, text: str) -> bool:
        """
        Check if the Open Forum section contains only administrative content.
        
        Args:
            text (str): Open Forum section text
            
        Returns:
            bool: True if section contains only administrative content
        """
        # Remove whitespace and newlines for analysis
        clean_text = re.sub(r'\s+', ' ', text.strip())
        
        # If the text is very short (likely just whitespace or minimal content)
        if len(clean_text) < 10:
            return True
        
        # Patterns that indicate administrative-only content
        admin_only_patterns = [
            r'^[A-Za-z0-9\s\-:]+envelope\s+id[:\s]*[A-Za-z0-9\-]+\s*$',  # Just Docusign ID
            r'^page\s+\d+\s*$',  # Just page number
            r'^continued\s*$',  # Just "continued"
            r'^end\s*$',  # Just "end"
            r'^\s*$',  # Just whitespace
        ]
        
        for pattern in admin_only_patterns:
            if re.match(pattern, clean_text, re.IGNORECASE):
                return True
        
        # If text only contains common administrative phrases
        admin_words = ['docusign', 'envelope', 'id', 'page', 'continued', 'end']
        words = clean_text.lower().split()
        non_admin_words = [w for w in words if not any(admin in w for admin in admin_words)]
        
        # If less than 3 non-administrative words, likely admin-only
        if len(non_admin_words) < 3:
            return True
        
        return False
    
    def is_admin_paragraph(self, paragraph: str) -> bool:
        """
        Check if a paragraph is administrative content rather than a public comment.
        
        Args:
            paragraph (str): Paragraph text
            
        Returns:
            bool: True if paragraph is administrative content
        """
        clean_para = paragraph.strip().lower()
        
        # If the paragraph is very short and only contains admin content
        if len(clean_para) < 50:
            admin_patterns = [
                r'docusign\s+envelope\s+id:',
                r'page\s+\d+',
                r'^continued\s*$',
                r'^end\s*$',
                r'^\s*\d+\s*$',  # Just numbers
                r'meeting\s+id:',
                r'zoom\s+call:',
                r'passcode:',
            ]
            
            for pattern in admin_patterns:
                if re.search(pattern, clean_para):
                    return True
        
        # For longer paragraphs, check if it's MOSTLY administrative content
        # If it has substantial meaningful content beyond admin phrases, it's likely a real comment
        if len(clean_para) > 100:
            # Remove common admin phrases and see what's left
            temp_text = re.sub(r'docusign\s+envelope\s+id:\s*[a-f0-9\-]+', '', clean_para, flags=re.IGNORECASE)
            temp_text = re.sub(r'page\s+\d+', '', temp_text, flags=re.IGNORECASE)
            temp_text = re.sub(r'meeting\s+id:\s*\d+', '', temp_text, flags=re.IGNORECASE)
            temp_text = re.sub(r'zoom\s+call:\s*https?://[^\s]+', '', temp_text, flags=re.IGNORECASE)
            temp_text = re.sub(r'passcode:\s*\w+', '', temp_text, flags=re.IGNORECASE)
            
            # Clean up extra whitespace
            temp_text = re.sub(r'\s+', ' ', temp_text).strip()
            
            # If there's substantial content left after removing admin phrases, it's a real comment
            if len(temp_text) > 80:  # Threshold for meaningful content
                return False
        
        return False
    
    def extract_date_from_filename(self, filename: str) -> str:
        """
        Universal date extraction from filename using multiple approaches.
        
        This function is designed to be 99%+ accurate even with wildly varying formats.
        It uses multiple strategies in order of reliability.
        
        Args:
            filename (str): PDF filename
            
        Returns:
            str: Formatted date (MM.DD.YYYY) or "Unknown Date"
        """
        import datetime
        
        # Strategy 1: Find all potential date patterns in the filename
        # This covers virtually every conceivable format
        date_patterns = [
            # Standard formats with various separators
            r'(\d{1,2})[.\-_/](\d{1,2})[.\-_/](\d{4})',     # M.D.YYYY, M-D-YYYY, M_D_YYYY, M/D/YYYY
            r'(\d{1,2})[.\-_/](\d{1,2})[.\-_/](\d{2})',      # M.D.YY, M-D-YY, M_D_YY, M/D/YY
            r'(\d{4})[.\-_/](\d{1,2})[.\-_/](\d{1,2})',      # YYYY.M.D, YYYY-M-D, etc.
            
            # With spaces before/after separators
            r'\s+(\d{1,2})[.\-_/]\s*(\d{1,2})[.\-_/]\s*(\d{4})',  # " M. D. YYYY"
            r'\s+(\d{1,2})[.\-_/]\s*(\d{1,2})[.\-_/]\s*(\d{2})',   # " M. D. YY"
            r'(\d{1,2})\s*[.\-_/]\s*(\d{1,2})\s*[.\-_/]\s*(\d{4})', # "M . D . YYYY"
            r'(\d{1,2})\s*[.\-_/]\s*(\d{1,2})\s*[.\-_/]\s*(\d{2})',  # "M . D . YY"
            
            # Compact formats (no separators)
            r'(\d{2})(\d{2})(\d{4})',    # MMDDYYYY
            r'(\d{1})(\d{2})(\d{4})',    # MDDYYYY  
            r'(\d{2})(\d{1})(\d{4})',    # MMDYYYY
            r'(\d{1})(\d{1})(\d{4})',    # MDYYYY
            r'(\d{2})(\d{2})(\d{2})',    # MMDDYY
            
            # With various word separators around dates
            r'[a-zA-Z\s]+(\d{1,2})[.\-_/](\d{1,2})[.\-_/](\d{2,4})[a-zA-Z\s]*', # "Minutes 1.2.21 draft"
        ]
        
        # Strategy 2: Extract all potential date candidates
        candidates = []
        
        for pattern in date_patterns:
            matches = re.finditer(pattern, filename)
            for match in matches:
                groups = match.groups()
                if len(groups) == 3:
                    candidates.append(groups)
        
        # Strategy 3: Validate and normalize each candidate
        for candidate in candidates:
            try:
                # Determine which group is month, day, year based on values and positions
                g1, g2, g3 = candidate
                
                # Handle different year formats
                if len(g3) == 4:  # YYYY format
                    year = int(g3)
                    month, day = int(g1), int(g2)
                elif len(g3) == 2:  # YY format
                    year_short = int(g3)
                    year = 2000 + year_short if year_short <= 50 else 1900 + year_short
                    month, day = int(g1), int(g2)
                elif len(g1) == 4:  # YYYY.MM.DD format
                    year = int(g1)
                    month, day = int(g2), int(g3)
                else:
                    continue  # Skip invalid formats
                
                # Validate month and day ranges
                if not (1 <= month <= 12):
                    # Try swapping month and day if original month is invalid
                    if 1 <= day <= 12:
                        month, day = day, month
                    else:
                        continue
                        
                if not (1 <= day <= 31):
                    continue
                
                # Additional validation: check if the date is reasonable for meeting minutes
                if not (1990 <= year <= 2030):
                    continue
                
                # Try to create a valid date to ensure it's real (handles Feb 30, etc.)
                try:
                    datetime.date(year, month, day)
                except ValueError:
                    continue
                
                # Format as MM.DD.YYYY
                return f"{month:02d}.{day:02d}.{year}"
                
            except (ValueError, IndexError):
                continue
        
        # Strategy 4: Look for month names (January, Jan, etc.)
        month_patterns = {
            r'\b(jan|january)\b.*?(\d{1,2}).*?(\d{2,4})': 1,
            r'\b(feb|february)\b.*?(\d{1,2}).*?(\d{2,4})': 2,
            r'\b(mar|march)\b.*?(\d{1,2}).*?(\d{2,4})': 3,
            r'\b(apr|april)\b.*?(\d{1,2}).*?(\d{2,4})': 4,
            r'\b(may)\b.*?(\d{1,2}).*?(\d{2,4})': 5,
            r'\b(jun|june)\b.*?(\d{1,2}).*?(\d{2,4})': 6,
            r'\b(jul|july)\b.*?(\d{1,2}).*?(\d{2,4})': 7,
            r'\b(aug|august)\b.*?(\d{1,2}).*?(\d{2,4})': 8,
            r'\b(sep|september)\b.*?(\d{1,2}).*?(\d{2,4})': 9,
            r'\b(oct|october)\b.*?(\d{1,2}).*?(\d{2,4})': 10,
            r'\b(nov|november)\b.*?(\d{1,2}).*?(\d{2,4})': 11,
            r'\b(dec|december)\b.*?(\d{1,2}).*?(\d{2,4})': 12,
        }
        
        filename_lower = filename.lower()
        for pattern, month in month_patterns.items():
            match = re.search(pattern, filename_lower)
            if match:
                try:
                    day = int(match.group(2))
                    year_str = match.group(3)
                    year = int(year_str)
                    if len(year_str) == 2:
                        year = 2000 + year if year <= 50 else 1900 + year
                    
                    if 1 <= day <= 31 and 1990 <= year <= 2030:
                        return f"{month:02d}.{day:02d}.{year}"
                except (ValueError, IndexError):
                    continue
        
        return "Unknown Date"
    
    def process_single_pdf(self, pdf_path: str) -> Tuple[str, Optional[int]]:
        """
        Process a single PDF file and extract comment count.
        
        Args:
            pdf_path (str): Path to the PDF file
            
        Returns:
            Tuple[str, Optional[int]]: (date, comment_count) or (date, None) if skipped
        """
        filename = os.path.basename(pdf_path)
        date = self.extract_date_from_filename(filename)
        
        if self.debug_mode:
            print(f"\nProcessing: {filename}")
            print(f"Extracted date: {date}")
        
        # Extract text from PDF
        text = self.extract_text_from_pdf(pdf_path)
        if not text:
            self.skipped_files.append((filename, "Failed to extract text"))
            return date, None
        
        # Extract Open Forum section
        open_forum_text = self.extract_open_forum_section(text)
        if not open_forum_text:
            self.skipped_files.append((filename, "No Open Forum section found"))
            return date, None
        
        # Count comments
        comment_count = self.count_public_comments(open_forum_text)
        
        if comment_count == 0:
            self.skipped_files.append((filename, "No comments or 'no comment' marker found"))
            return date, None
        
        return date, comment_count
    
    def process_folder(self, folder_path: str) -> Dict[str, Dict[str, int]]:
        """
        Process all PDF files in the given folder, organized by academic years.
        
        Args:
            folder_path (str): Path to folder containing yearly subfolders
            
        Returns:
            Dict[str, Dict[str, int]]: Dictionary mapping years to {dates: comment_counts}
        """
        if not os.path.exists(folder_path):
            raise FileNotFoundError(f"Folder not found: {folder_path}")
        
        yearly_results = {}
        self.meeting_stats = {}  # Store comprehensive meeting statistics
        total_pdf_files = 0
        
        # Find all yearly folders (e.g., 2020-2021, 2021-2022, etc.)
        yearly_folders = []
        for item in os.listdir(folder_path):
            item_path = os.path.join(folder_path, item)
            if os.path.isdir(item_path) and re.match(r'\d{4}-\d{4}', item):
                yearly_folders.append((item, item_path))
        
        yearly_folders.sort()  # Sort by year
        
        if not yearly_folders:
            print("No yearly folders found. Falling back to processing all PDF files in the folder...")
            return {"All Files": self.process_single_year_folder(folder_path)}
        
        print(f"Found {len(yearly_folders)} yearly folders: {[year for year, _ in yearly_folders]}")
        
        # Process each yearly folder
        for year_name, year_path in yearly_folders:
            print(f"\nProcessing academic year: {year_name}")
            
            # Look for Minutes subfolder within the year - handle both "Minutes" and "Minute"
            minutes_path = os.path.join(year_path, "Minutes")
            if not os.path.exists(minutes_path):
                # Try "Minute" (singular) as fallback
                minutes_path = os.path.join(year_path, "Minute")
                if not os.path.exists(minutes_path):
                    print(f"  No 'Minutes' or 'Minute' folder found in {year_name}, skipping...")
                    continue
            
            year_results, year_stats = self.process_single_year_folder_with_stats(minutes_path)
            yearly_results[year_name] = year_results
            self.meeting_stats[year_name] = year_stats
            
            year_file_count = sum(1 for _ in year_results.values())
            total_pdf_files += year_stats['total_meetings']
            
            print(f"  Found {year_file_count} files with comments in {year_name}")
        
        self.processing_stats['total_files'] = total_pdf_files
        
        return yearly_results
    
    def process_single_year_folder(self, folder_path: str) -> Dict[str, int]:
        """
        Process PDF files in a single folder (for one academic year).
        
        Args:
            folder_path (str): Path to folder containing PDF files
            
        Returns:
            Dict[str, int]: Dictionary mapping dates to comment counts
        """
        comment_count_map = {}
        pdf_files = []
        
        # Find all PDF files in this folder
        for root, _, files in os.walk(folder_path):
            for file in files:
                if file.lower().endswith('.pdf'):
                    pdf_files.append(os.path.join(root, file))
        
        if self.debug_mode:
            print(f"    Processing {len(pdf_files)} PDF files in {folder_path}")
        
        # Process each PDF file
        for pdf_path in pdf_files:
            date, comment_count = self.process_single_pdf(pdf_path)
            
            if comment_count is not None:
                comment_count_map[date] = comment_count
                self.processing_stats['processed_files'] += 1
                self.processing_stats['total_comments'] += comment_count
            else:
                self.processing_stats['skipped_files'] += 1
        
        return comment_count_map
    
    def process_single_year_folder_with_stats(self, folder_path: str) -> Tuple[Dict[str, int], Dict[str, int]]:
        """
        Process PDF files in a single folder with comprehensive statistics.
        
        Args:
            folder_path (str): Path to folder containing PDF files
            
        Returns:
            Tuple[Dict[str, int], Dict[str, int]]: (comment_counts, meeting_stats)
        """
        comment_count_map = {}
        pdf_files = []
        
        # Find all PDF files in this folder
        for root, _, files in os.walk(folder_path):
            for file in files:
                if file.lower().endswith('.pdf'):
                    pdf_files.append(os.path.join(root, file))
        
        total_meetings = len(pdf_files)
        meetings_with_comments = 0
        meetings_no_comments = 0
        meetings_no_open_forum = 0
        total_comments = 0
        
        if self.debug_mode:
            print(f"    Processing {len(pdf_files)} PDF files in {folder_path}")
        
        # Process each PDF file
        for pdf_path in pdf_files:
            filename = os.path.basename(pdf_path)
            date = self.extract_date_from_filename(filename)
            
            # Extract text from PDF
            text = self.extract_text_from_pdf(pdf_path)
            if not text:
                meetings_no_open_forum += 1
                continue
            
            # Extract Open Forum section
            open_forum_text = self.extract_open_forum_section(text)
            if not open_forum_text:
                meetings_no_open_forum += 1
                continue
            
            # Count comments
            comment_count = self.count_public_comments(open_forum_text)
            
            if comment_count > 0:
                comment_count_map[date] = comment_count
                meetings_with_comments += 1
                total_comments += comment_count
                self.processing_stats['processed_files'] += 1
                self.processing_stats['total_comments'] += comment_count
            else:
                meetings_no_comments += 1
                self.processing_stats['skipped_files'] += 1
        
        # Compile statistics
        stats = {
            'total_meetings': total_meetings,
            'meetings_with_comments': meetings_with_comments,
            'meetings_no_comments': meetings_no_comments,
            'meetings_no_open_forum': meetings_no_open_forum,
            'total_comments': total_comments
        }
        
        return comment_count_map, stats

    def export_to_csv(self, yearly_data: Dict[str, Dict[str, int]], output_path: str = "open_forum_summary.csv"):
        """
        Export results to CSV file, organized by academic years.
        
        Args:
            yearly_data (Dict[str, Dict[str, int]]): Yearly comment count data
            output_path (str): Output CSV file path
        """
        try:
            with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['Academic_Year', 'Date', 'Comment_Count'])
                
                # Sort by academic year and then by date
                for year in sorted(yearly_data.keys()):
                    year_data = yearly_data[year]
                    sorted_data = sorted(year_data.items(), key=lambda x: x[0])
                    for date, count in sorted_data:
                        writer.writerow([year, date, count])
            
            print(f"Results exported to: {output_path}")
            
        except Exception as e:
            print(f"Error exporting to CSV: {e}")
    
    def print_summary(self, yearly_data: Dict[str, Dict[str, int]]):
        """
        Print a comprehensive summary of the processing results, organized by academic years.
        
        Args:
            yearly_data (Dict[str, Dict[str, int]]): Yearly comment count data
        """
        print("\n" + "="*70)
        print("🎯 AI MINUTES AGENT - COMPREHENSIVE MEETING ANALYSIS")
        print("="*70)
        
        # Overall statistics
        total_all_meetings = sum(stats.get('total_meetings', 0) for stats in getattr(self, 'meeting_stats', {}).values())
        total_meetings_with_comments = sum(stats.get('meetings_with_comments', 0) for stats in getattr(self, 'meeting_stats', {}).values())
        total_all_comments = sum(stats.get('total_comments', 0) for stats in getattr(self, 'meeting_stats', {}).values())
        
        print(f"📊 OVERALL STATISTICS")
        print(f"Total meetings across all years: {total_all_meetings}")
        print(f"Meetings with public comments: {total_meetings_with_comments}")
        print(f"Meetings without public comments: {total_all_meetings - total_meetings_with_comments}")
        if total_all_meetings > 0:
            participation_rate = (total_meetings_with_comments / total_all_meetings) * 100
            print(f"Public participation rate: {participation_rate:.1f}%")
        print(f"Total public comments found: {total_all_comments}")
        
        if yearly_data and hasattr(self, 'meeting_stats'):
            print(f"\n📅 YEARLY BREAKDOWN:")
            print("="*70)
            
            for year in sorted(yearly_data.keys()):
                year_data = yearly_data[year]
                year_stats = self.meeting_stats.get(year, {})
                
                total_meetings = year_stats.get('total_meetings', 0)
                meetings_with_comments = year_stats.get('meetings_with_comments', 0)
                meetings_no_comments = year_stats.get('meetings_no_comments', 0)
                meetings_no_open_forum = year_stats.get('meetings_no_open_forum', 0)
                total_comments = year_stats.get('total_comments', 0)
                
                if total_meetings > 0:
                    participation_rate = (meetings_with_comments / total_meetings) * 100
                    print(f"\n📅 {year}")
                    print(f"📋 Total meetings held: {total_meetings}")
                    print(f"💬 Meetings with public comments: {meetings_with_comments}")
                    print(f"🚫 Meetings with no comments: {meetings_no_comments}")
                    print(f"❌ Meetings with no Open Forum: {meetings_no_open_forum}")
                    print(f"📈 Public participation rate: {participation_rate:.1f}%")
                    print(f"💯 Total comments: {total_comments}")
                    print("-" * 50)
                    
                    if year_data:
                        sorted_data = sorted(year_data.items(), key=lambda x: x[0])
                        for date, count in sorted_data:
                            print(f"  📝 {date}: {count} comment{'s' if count != 1 else ''}")
                    else:
                        print("  (No meetings with public comments)")
                else:
                    print(f"\n📅 {year}: No meeting data found")
        
        # Summary statistics table
        print(f"\n" + "="*70)
        print("📈 PARTICIPATION SUMMARY TABLE")
        print("="*70)
        print(f"{'Year':<12} {'Total':<7} {'w/Comments':<12} {'Rate':<8} {'Comments':<10}")
        print("-" * 70)
        
        if hasattr(self, 'meeting_stats'):
            for year in sorted(yearly_data.keys()):
                year_stats = self.meeting_stats.get(year, {})
                total = year_stats.get('total_meetings', 0)
                with_comments = year_stats.get('meetings_with_comments', 0)
                total_comments = year_stats.get('total_comments', 0)
                rate = (with_comments / total * 100) if total > 0 else 0
                
                print(f"{year:<12} {total:<7} {with_comments:<12} {rate:<7.1f}% {total_comments:<10}")
        
        # Final totals
        print("-" * 70)
        print(f"{'TOTAL':<12} {total_all_meetings:<7} {total_meetings_with_comments:<12} {(total_meetings_with_comments/total_all_meetings*100) if total_all_meetings > 0 else 0:<7.1f}% {total_all_comments:<10}")
        
        if self.skipped_files and self.debug_mode:
            print(f"\n🔍 DETAILED SKIP REASONS ({len(self.skipped_files)} files):")
            print("-" * 50)
            for filename, reason in self.skipped_files:
                print(f"- {filename}: {reason}")
        
        print(f"\n🎉 Analysis complete! Check the results above for insights into public participation patterns.")
        print("="*70)


def main():
    """
    Main function to run the AI Minutes Agent.
    """
    parser = argparse.ArgumentParser(
        description="AI agent for extracting public comments from committee meeting minutes"
    )
    parser.add_argument(
        "folder_path",
        help="Path to folder containing PDF meeting minutes"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode for detailed processing output"
    )
    parser.add_argument(
        "--export-csv",
        action="store_true",
        help="Export results to CSV file"
    )
    parser.add_argument(
        "--csv-output",
        default="open_forum_summary.csv",
        help="Output CSV filename (default: open_forum_summary.csv)"
    )
    
    args = parser.parse_args()
    
    # Initialize the agent
    agent = AIMinutesAgent(debug_mode=args.debug)
    
    try:
        # Process the folder
        print(f"Starting AI Minutes Agent...")
        print(f"Processing folder: {args.folder_path}")
        
        yearly_data = agent.process_folder(args.folder_path)
        
        # Print summary
        agent.print_summary(yearly_data)
        
        # Export to CSV if requested
        if args.export_csv:
            agent.export_to_csv(yearly_data, args.csv_output)
        
        # Return the results
        return yearly_data
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
