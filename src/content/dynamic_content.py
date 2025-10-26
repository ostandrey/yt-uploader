"""
Dynamic content sources for YouTube automation project.
Fetches real-time content from RSS feeds, news APIs, and social media.
"""

import os
import requests
import feedparser
import json
import random
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import time
import re

from logger import get_logger

class DynamicContentFetcher:
    """Fetches dynamic content from various sources."""
    
    def __init__(self):
        self.logger = get_logger()
        
        # Tech news RSS feeds
        self.tech_feeds = {
            'techcrunch': 'https://techcrunch.com/feed/',
            'the_verge': 'https://www.theverge.com/rss/index.xml',
            'wired': 'https://www.wired.com/feed/rss',
            'ars_technica': 'https://feeds.arstechnica.com/arstechnica/index/',
            'engadget': 'https://www.engadget.com/rss.xml',
            'mashable': 'https://mashable.com/feeds/rss/all',
            'venturebeat': 'https://venturebeat.com/feed/',
            'zdnet': 'https://www.zdnet.com/topic/artificial-intelligence/rss.xml'
        }
        
        # News API endpoints (if API keys are available)
        self.news_apis = {
            'newsapi': 'https://newsapi.org/v2/everything',
            'guardian': 'https://content.guardianapis.com/search'
        }
    
    def get_trending_tech_topics(self, count: int = 5) -> List[Dict]:
        """Get trending tech topics from RSS feeds."""
        try:
            all_articles = []
            
            # Fetch from multiple RSS feeds
            for source, feed_url in self.tech_feeds.items():
                try:
                    articles = self._fetch_rss_feed(feed_url, source)
                    all_articles.extend(articles)
                    time.sleep(0.5)  # Rate limiting
                except Exception as e:
                    self.logger.log_warning(f"Failed to fetch from {source}: {e}")
                    continue
            
            # Filter and rank articles
            trending_topics = self._rank_and_filter_articles(all_articles, count)
            
            self.logger.log_info(f"Found {len(trending_topics)} trending tech topics")
            return trending_topics
            
        except Exception as e:
            self.logger.log_error(f"Failed to get trending topics: {e}")
            return []
    
    def _fetch_rss_feed(self, feed_url: str, source: str) -> List[Dict]:
        """Fetch articles from a single RSS feed."""
        try:
            feed = feedparser.parse(feed_url)
            articles = []
            
            for entry in feed.entries[:10]:  # Limit to 10 per feed
                # Extract relevant information
                article = {
                    'title': entry.get('title', ''),
                    'summary': entry.get('summary', ''),
                    'link': entry.get('link', ''),
                    'published': entry.get('published_parsed', None),
                    'source': source,
                    'category': self._categorize_article(entry.get('title', '') + ' ' + entry.get('summary', ''))
                }
                
                # Only include recent articles (last 7 days)
                if article['published']:
                    pub_date = datetime(*article['published'][:6])
                    if pub_date > datetime.now() - timedelta(days=7):
                        articles.append(article)
            
            return articles
            
        except Exception as e:
            self.logger.log_warning(f"Failed to parse RSS feed {feed_url}: {e}")
            return []
    
    def _categorize_article(self, text: str) -> str:
        """Categorize article based on content."""
        text_lower = text.lower()
        
        categories = {
            'AI': ['artificial intelligence', 'ai', 'machine learning', 'ml', 'chatgpt', 'openai', 'neural network'],
            'Mobile': ['iphone', 'android', 'smartphone', 'mobile', 'ios', 'app store', 'google play'],
            'Gaming': ['gaming', 'game', 'playstation', 'xbox', 'nintendo', 'steam', 'esports'],
            'Hardware': ['cpu', 'gpu', 'processor', 'chip', 'intel', 'amd', 'nvidia', 'hardware'],
            'Software': ['software', 'app', 'update', 'release', 'bug', 'feature', 'programming'],
            'Startup': ['startup', 'funding', 'investment', 'venture', 'unicorn', 'ipo'],
            'Security': ['security', 'hack', 'breach', 'cybersecurity', 'privacy', 'encryption'],
            'Social Media': ['facebook', 'twitter', 'instagram', 'tiktok', 'social media', 'meta']
        }
        
        for category, keywords in categories.items():
            if any(keyword in text_lower for keyword in keywords):
                return category
        
        return 'General'
    
    def _rank_and_filter_articles(self, articles: List[Dict], count: int) -> List[Dict]:
        """Rank articles by relevance and recency."""
        try:
            # Score articles based on various factors
            scored_articles = []
            
            for article in articles:
                score = 0
                
                # Recency score (newer = higher score)
                if article['published']:
                    pub_date = datetime(*article['published'][:6])
                    days_old = (datetime.now() - pub_date).days
                    score += max(0, 10 - days_old)  # 10 points for today, decreasing
                
                # Category relevance
                high_interest_categories = ['AI', 'Mobile', 'Gaming', 'Hardware', 'Startup']
                if article['category'] in high_interest_categories:
                    score += 5
                
                # Title quality (length, keywords)
                title = article['title']
                if len(title) > 20 and len(title) < 100:  # Good length
                    score += 2
                
                # Tech keywords boost
                tech_keywords = ['new', 'latest', 'breakthrough', 'innovation', 'update', 'release']
                if any(keyword in title.lower() for keyword in tech_keywords):
                    score += 3
                
                article['score'] = score
                scored_articles.append(article)
            
            # Sort by score and return top articles
            scored_articles.sort(key=lambda x: x['score'], reverse=True)
            return scored_articles[:count]
            
        except Exception as e:
            self.logger.log_warning(f"Failed to rank articles: {e}")
            return articles[:count]
    
    def generate_content_from_topic(self, topic_data: Dict) -> Dict:
        """Generate video content from a trending topic."""
        try:
            title = topic_data['title']
            summary = topic_data.get('summary', '')
            category = topic_data.get('category', 'General')
            
            # Create engaging script based on the topic
            script = self._create_script_from_topic(title, summary, category)
            
            # Generate title, description, and tags
            video_title = self._generate_video_title(title, category)
            description = self._generate_description(title, summary, topic_data.get('link', ''))
            tags = self._generate_tags(category, title)
            
            return {
                'script': script,
                'title': video_title,
                'description': description,
                'tags': tags,
                'source': topic_data.get('source', ''),
                'original_link': topic_data.get('link', ''),
                'category': category
            }
            
        except Exception as e:
            self.logger.log_error(f"Failed to generate content from topic: {e}")
            return {}
    
    def _create_script_from_topic(self, title: str, summary: str, category: str) -> str:
        """Create an engaging script from topic data."""
        try:
            # Clean and extract key information
            clean_title = re.sub(r'<[^>]+>', '', title)  # Remove HTML tags
            clean_summary = re.sub(r'<[^>]+>', '', summary)
            
            # Create engaging opening
            openings = {
                'AI': "Breaking news in artificial intelligence!",
                'Mobile': "Major mobile tech update just dropped!",
                'Gaming': "Gamers, this is huge news!",
                'Hardware': "Hardware enthusiasts, listen up!",
                'Startup': "Startup world just got exciting!",
                'Security': "Important security update everyone needs to know!",
                'Software': "Software update that changes everything!",
                'General': "Tech world is buzzing with this news!"
            }
            
            opening = openings.get(category, openings['General'])
            
            # Create the main content
            if clean_summary and len(clean_summary) > 50:
                # Use the summary if available
                main_content = clean_summary[:300] + "..." if len(clean_summary) > 300 else clean_summary
            else:
                # Create content from title
                main_content = f"{clean_title}. This development is shaking up the tech industry and could impact how we use technology in our daily lives."
            
            # Create engaging closing
            closings = [
                "What do you think about this development? Let us know in the comments!",
                "This is definitely something to watch in the coming weeks!",
                "Stay tuned for more updates on this story!",
                "The tech world never stops evolving, and this proves it!"
            ]
            
            closing = random.choice(closings)
            
            # Combine into full script
            script = f"{opening} {main_content} {closing}"
            
            # Ensure script is appropriate length (30-60 seconds of speech)
            if len(script) < 200:
                script += " This is a developing story that we'll continue to follow closely."
            elif len(script) > 500:
                script = script[:500] + "..."
            
            return script
            
        except Exception as e:
            self.logger.log_warning(f"Failed to create script: {e}")
            return f"Breaking tech news: {title}. This is a developing story in the tech world."
    
    def _generate_video_title(self, original_title: str, category: str) -> str:
        """Generate an engaging video title."""
        try:
            # Clean the original title
            clean_title = re.sub(r'<[^>]+>', '', original_title)
            clean_title = clean_title.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
            
            # Create engaging prefixes
            prefixes = {
                'AI': ["🤖 AI BREAKTHROUGH:", "🚀 AI NEWS:", "⚡ AI UPDATE:"],
                'Mobile': ["📱 MOBILE NEWS:", "🔥 PHONE UPDATE:", "📲 TECH BREAKING:"],
                'Gaming': ["🎮 GAMING NEWS:", "🕹️ GAME UPDATE:", "🎯 GAMING BREAK:"],
                'Hardware': ["💻 HARDWARE NEWS:", "🔧 TECH HARDWARE:", "⚙️ HARDWARE UPDATE:"],
                'Startup': ["🚀 STARTUP NEWS:", "💡 INNOVATION:", "🌟 STARTUP BREAK:"],
                'Security': ["🔒 SECURITY ALERT:", "🛡️ CYBERSECURITY:", "⚠️ SECURITY NEWS:"],
                'Software': ["💻 SOFTWARE UPDATE:", "🔧 APP NEWS:", "📱 SOFTWARE BREAK:"],
                'General': ["🔥 TECH NEWS:", "⚡ BREAKING TECH:", "📰 TECH UPDATE:"]
            }
            
            prefix_options = prefixes.get(category, prefixes['General'])
            prefix = random.choice(prefix_options)
            
            # Truncate title if too long (keep it under 50 chars for validation)
            max_length = 45  # Shorter to account for prefix
            if len(clean_title) > max_length:
                clean_title = clean_title[:max_length-3] + "..."
            
            video_title = f"{prefix} {clean_title}"
            
            # Ensure total length is under validation limit (60 chars)
            if len(video_title) > 60:
                video_title = video_title[:57] + "..."
            
            return video_title
            
        except Exception as e:
            self.logger.log_warning(f"Failed to generate video title: {e}")
            return f"Tech News: {original_title[:50]}"
    
    def _generate_description(self, title: str, summary: str, link: str) -> str:
        """Generate video description."""
        try:
            clean_title = re.sub(r'<[^>]+>', '', title)
            clean_summary = re.sub(r'<[^>]+>', '', summary)
            
            # Create description
            description = f"🔥 {clean_title}\n\n"
            
            if clean_summary and len(clean_summary) > 20:
                description += f"{clean_summary[:300]}\n\n"
            
            # Add hashtags
            hashtags = ["#TechNews", "#Technology", "#Innovation", "#TechUpdate", "#BreakingNews"]
            description += " ".join(hashtags)
            
            # Add source link if available
            if link:
                description += f"\n\nSource: {link}"
            
            # Ensure description is under YouTube's limit
            if len(description) > 5000:
                description = description[:4997] + "..."
            
            return description
            
        except Exception as e:
            self.logger.log_warning(f"Failed to generate description: {e}")
            return f"Tech news update: {title}\n\n#TechNews #Technology #Innovation"
    
    def _generate_tags(self, category: str, title: str) -> List[str]:
        """Generate relevant tags."""
        try:
            # Base tags
            base_tags = ["tech", "technology", "news", "innovation", "update"]
            
            # Category-specific tags
            category_tags = {
                'AI': ["artificial intelligence", "ai", "machine learning", "chatgpt", "openai"],
                'Mobile': ["mobile", "smartphone", "iphone", "android", "apps"],
                'Gaming': ["gaming", "games", "esports", "playstation", "xbox"],
                'Hardware': ["hardware", "cpu", "gpu", "intel", "amd", "nvidia"],
                'Startup': ["startup", "funding", "investment", "venture capital"],
                'Security': ["security", "cybersecurity", "privacy", "hack"],
                'Software': ["software", "apps", "programming", "development"],
                'General': ["tech news", "breaking news", "industry update"]
            }
            
            tags = base_tags + category_tags.get(category, category_tags['General'])
            
            # Add tags from title
            title_words = re.findall(r'\b\w+\b', title.lower())
            for word in title_words:
                if len(word) > 3 and word not in ['the', 'and', 'for', 'with', 'this', 'that']:
                    tags.append(word)
            
            # Remove duplicates and limit to 15 tags
            unique_tags = list(dict.fromkeys(tags))[:15]
            
            return unique_tags
            
        except Exception as e:
            self.logger.log_warning(f"Failed to generate tags: {e}")
            return ["tech", "technology", "news", "innovation"]
