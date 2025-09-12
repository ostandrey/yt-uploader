"""
Visual content fetching script for YouTube automation project.
Fetches images and videos from stock APIs (Pexels, Pixabay, Unsplash) with fallback to AI generation.
"""

import os
import requests
import json
import random
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import time

from logger import get_logger

class VisualContentFetcher:
    def __init__(self, pexels_api_key: str, pixabay_api_key: str, 
                 unsplash_access_key: str, abacus_api_key: Optional[str] = None):
        """
        Initialize visual content fetcher with API keys.
        
        Args:
            pexels_api_key: Pexels API key
            pixabay_api_key: Pixabay API key
            unsplash_access_key: Unsplash access key
            abacus_api_key: Abacus.AI API key for fallback generation
        """
        self.pexels_api_key = pexels_api_key
        self.pixabay_api_key = pixabay_api_key
        self.unsplash_access_key = unsplash_access_key
        self.abacus_api_key = abacus_api_key
        self.logger = get_logger()
        
        # API endpoints
        self.pexels_url = "https://api.pexels.com/v1"
        self.pixabay_url = "https://pixabay.com/api"
        self.unsplash_url = "https://api.unsplash.com"
        
        # Headers
        self.pexels_headers = {"Authorization": pexels_api_key}
        self.pixabay_headers = {}
        self.unsplash_headers = {"Authorization": f"Client-ID {unsplash_access_key}"}
    
    def get_visuals_for_script(self, content: Dict, channel_config: Dict, 
                              count: int = 5) -> List[Dict]:
        """
        Get visual content for a script based on channel configuration.
        
        Args:
            content: The content dictionary with script, title, etc.
            channel_config: Channel configuration
            count: Number of visuals to fetch
            
        Returns:
            List of visual content dictionaries
        """
        try:
            # Extract script text from content dictionary
            script_text = content.get('script', '')
            if not script_text:
                script_text = content.get('title', '') + ' ' + content.get('description', '')
            
            visual_source = channel_config.get("settings", {}).get("visual_source", "mixed")
            keywords = self._extract_keywords(script_text)
            
            visuals = []
            
            if visual_source == "stock":
                visuals = self._fetch_stock_content(keywords, count)
            elif visual_source == "generated":
                visuals = self._generate_ai_content(keywords, count)
            else:  # mixed
                # Try stock first, fallback to AI generation, then placeholder
                visuals = self._fetch_stock_content(keywords, count)
                if len(visuals) < count and self.abacus_api_key:
                    remaining = count - len(visuals)
                    ai_visuals = self._generate_ai_content(keywords, remaining)
                    visuals.extend(ai_visuals)
                
                # If still no visuals, create placeholder visuals
                if len(visuals) == 0:
                    visuals = self._create_placeholder_visuals(keywords, count)
            
            self.logger.log_info(
                f"Fetched {len(visuals)} visuals for {channel_config['channel_name']}"
            )
            
            return visuals[:count]  # Ensure we don't exceed requested count
            
        except Exception as e:
            self.logger.log_error(
                f"Failed to get visuals for {channel_config['channel_name']}: {e}"
            )
            return []
    
    def _extract_keywords(self, script: str) -> List[str]:
        """Extract keywords from script for visual search."""
        # Simple keyword extraction - can be enhanced with NLP
        words = script.lower().split()
        
        # Remove common words
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have',
            'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should',
            'may', 'might', 'must', 'can', 'this', 'that', 'these', 'those'
        }
        
        keywords = [word for word in words if word not in stop_words and len(word) > 3]
        
        # Get unique keywords, limit to 5
        unique_keywords = list(set(keywords))[:5]
        
        return unique_keywords if unique_keywords else ["technology", "news", "update"]
    
    def _fetch_stock_content(self, keywords: List[str], count: int) -> List[Dict]:
        """Fetch content from stock APIs."""
        visuals = []
        
        # Try each API in order of preference
        apis = [
            ("pexels", self._fetch_from_pexels),
            ("pixabay", self._fetch_from_pixabay),
            ("unsplash", self._fetch_from_unsplash)
        ]
        
        for api_name, fetch_func in apis:
            if len(visuals) >= count:
                break
                
            try:
                remaining = count - len(visuals)
                api_visuals = fetch_func(keywords, remaining)
                visuals.extend(api_visuals)
                
                if api_visuals:
                    self.logger.log_info(f"Fetched {len(api_visuals)} visuals from {api_name}")
                    
            except Exception as e:
                self.logger.log_warning(f"Failed to fetch from {api_name}: {e}")
                continue
        
        return visuals
    
    def _fetch_from_pexels(self, keywords: List[str], count: int) -> List[Dict]:
        """Fetch images from Pexels API."""
        visuals = []
        
        for keyword in keywords:
            if len(visuals) >= count:
                break
                
            try:
                url = f"{self.pexels_url}/search"
                params = {
                    "query": keyword,
                    "per_page": min(count, 15),
                    "orientation": "portrait"  # Good for Shorts
                }
                
                response = requests.get(url, headers=self.pexels_headers, params=params, timeout=10)
                response.raise_for_status()
                
                data = response.json()
                
                for photo in data.get("photos", []):
                    if len(visuals) >= count:
                        break
                        
                    visual = {
                        "url": photo["src"]["large"],
                        "thumbnail": photo["src"]["medium"],
                        "alt": photo.get("alt", keyword),
                        "photographer": photo["photographer"],
                        "source": "pexels",
                        "keyword": keyword,
                        "type": "image"
                    }
                    visuals.append(visual)
                    
            except Exception as e:
                self.logger.log_warning(f"Pexels API error for keyword '{keyword}': {e}")
                continue
        
        return visuals
    
    def _fetch_from_pixabay(self, keywords: List[str], count: int) -> List[Dict]:
        """Fetch images from Pixabay API."""
        visuals = []
        
        for keyword in keywords:
            if len(visuals) >= count:
                break
                
            try:
                url = self.pixabay_url
                params = {
                    "key": self.pixabay_api_key,
                    "q": keyword,
                    "image_type": "photo",
                    "orientation": "vertical",
                    "per_page": min(count, 20),
                    "safesearch": "true"
                }
                
                response = requests.get(url, params=params, timeout=10)
                response.raise_for_status()
                
                data = response.json()
                
                for hit in data.get("hits", []):
                    if len(visuals) >= count:
                        break
                        
                    visual = {
                        "url": hit["webformatURL"],
                        "thumbnail": hit["previewURL"],
                        "alt": hit.get("tags", keyword),
                        "photographer": hit.get("user", "Unknown"),
                        "source": "pixabay",
                        "keyword": keyword,
                        "type": "image"
                    }
                    visuals.append(visual)
                    
            except Exception as e:
                self.logger.log_warning(f"Pixabay API error for keyword '{keyword}': {e}")
                continue
        
        return visuals
    
    def _fetch_from_unsplash(self, keywords: List[str], count: int) -> List[Dict]:
        """Fetch images from Unsplash API."""
        visuals = []
        
        for keyword in keywords:
            if len(visuals) >= count:
                break
                
            try:
                url = f"{self.unsplash_url}/search/photos"
                params = {
                    "query": keyword,
                    "per_page": min(count, 10),
                    "orientation": "portrait"
                }
                
                response = requests.get(url, headers=self.unsplash_headers, params=params, timeout=10)
                response.raise_for_status()
                
                data = response.json()
                
                for photo in data.get("results", []):
                    if len(visuals) >= count:
                        break
                        
                    visual = {
                        "url": photo["urls"]["regular"],
                        "thumbnail": photo["urls"]["thumb"],
                        "alt": photo.get("alt_description", keyword),
                        "photographer": photo["user"]["name"],
                        "source": "unsplash",
                        "keyword": keyword,
                        "type": "image"
                    }
                    visuals.append(visual)
                    
            except Exception as e:
                self.logger.log_warning(f"Unsplash API error for keyword '{keyword}': {e}")
                continue
        
        return visuals
    
    def _generate_ai_content(self, keywords: List[str], count: int) -> List[Dict]:
        """Generate visual content using AI (Abacus.AI)."""
        if not self.abacus_api_key:
            self.logger.log_warning("Abacus.AI API key not available for image generation")
            return []
        
        visuals = []
        
        try:
            # This is a placeholder - replace with actual Abacus.AI image generation API
            for i, keyword in enumerate(keywords[:count]):
                prompt = f"Create an engaging image for YouTube Short about: {keyword}"
                
                # Placeholder for Abacus.AI image generation
                # You'll need to implement the actual API call based on Abacus.AI documentation
                visual = {
                    "url": f"generated_image_{i}.jpg",  # Placeholder
                    "thumbnail": f"generated_thumb_{i}.jpg",  # Placeholder
                    "alt": f"AI generated image for {keyword}",
                    "photographer": "AI Generated",
                    "source": "abacus_ai",
                    "keyword": keyword,
                    "type": "image"
                }
                visuals.append(visual)
                
            self.logger.log_info(f"Generated {len(visuals)} AI visuals")
            
        except Exception as e:
            self.logger.log_error(f"AI image generation failed: {e}")
        
        return visuals
    
    def download_visual(self, visual: Dict, download_dir: str) -> Optional[str]:
        """
        Download a visual to local storage.
        
        Args:
            visual: Visual content dictionary
            download_dir: Directory to save the file
            
        Returns:
            Local file path if successful, None otherwise
        """
        try:
            os.makedirs(download_dir, exist_ok=True)
            
            # Generate filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{visual['source']}_{visual['keyword']}_{timestamp}.jpg"
            filepath = os.path.join(download_dir, filename)
            
            # Download the image
            response = requests.get(visual["url"], timeout=30)
            response.raise_for_status()
            
            # Save to file
            with open(filepath, 'wb') as f:
                f.write(response.content)
            
            self.logger.log_info(f"Downloaded visual: {filename}")
            return filepath
            
        except Exception as e:
            self.logger.log_error(f"Failed to download visual: {e}")
            return None
    
    def get_thumbnail_for_video(self, script: str, channel_config: Dict) -> Optional[str]:
        """
        Get or generate a thumbnail for the video.
        
        Args:
            script: Video script
            channel_config: Channel configuration
            
        Returns:
            Path to thumbnail image or None
        """
        try:
            keywords = self._extract_keywords(script)
            channel_name = channel_config["channel_name"]
            
            # Try to get a good visual for thumbnail
            visuals = self._fetch_stock_content(keywords, 1)
            
            if visuals:
                visual = visuals[0]
                download_dir = f"storage/{channel_name.lower().replace(' ', '_')}/thumbnails"
                thumbnail_path = self.download_visual(visual, download_dir)
                
                if thumbnail_path:
                    self.logger.log_info(f"Generated thumbnail for {channel_name}")
                    return thumbnail_path
            
            # Fallback: generate AI thumbnail
            if self.abacus_api_key:
                # Placeholder for AI thumbnail generation
                self.logger.log_info(f"Using AI-generated thumbnail for {channel_name}")
                return None  # Implement AI thumbnail generation
            
            return None
            
        except Exception as e:
            self.logger.log_error(f"Failed to generate thumbnail: {e}")
            return None

# Example usage
if __name__ == "__main__":
    # Test configuration
    config = {
        "channel_name": "Tech News",
        "settings": {
            "visual_source": "mixed"
        }
    }
    
    # Initialize logger
    from logger import initialize_logger
    initialize_logger()
    
    # Test visual fetcher
    fetcher = VisualContentFetcher(
        pexels_api_key="your_pexels_key",
        pixabay_api_key="your_pixabay_key",
        unsplash_access_key="your_unsplash_key",
        abacus_api_key="your_abacus_key"
    )
    
    # Test with sample script
    script = "Today we're talking about the latest AI breakthrough in machine learning technology."
    visuals = fetcher.get_visuals_for_script(script, config, 3)
    
    print(f"Found {len(visuals)} visuals:")
    for visual in visuals:
        print(f"- {visual['source']}: {visual['alt']}")
