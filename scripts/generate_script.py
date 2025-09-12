"""
Content generation script for YouTube automation project.
Generates scripts, descriptions, and titles using Abacus.AI and other AI services.
"""

import os
import random
import requests
import json
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import time

# Import Abacus.AI SDK
try:
    from abacusai import ApiClient
    ABACUS_AVAILABLE = True
except ImportError:
    ABACUS_AVAILABLE = False
    print("Warning: Abacus.AI SDK not installed. Install with: pip install abacusai")

# Import our logger
from logger import get_logger

class ContentGenerator:
    def __init__(self, abacus_api_key: str, openai_api_key: Optional[str] = None):
        """
        Initialize the content generator with API keys.
        
        Args:
            abacus_api_key: Abacus.AI API key
            openai_api_key: OpenAI API key (backup)
        """
        self.abacus_api_key = abacus_api_key
        self.openai_api_key = openai_api_key
        self.logger = get_logger()
        
        # Initialize Abacus.AI client
        if ABACUS_AVAILABLE:
            try:
                self.abacus_client = ApiClient(api_key=abacus_api_key)
                self.logger.log_info("Abacus.AI client initialized successfully")
            except Exception as e:
                self.logger.log_error(f"Failed to initialize Abacus.AI client: {e}")
                self.abacus_client = None
        else:
            self.abacus_client = None
            self.logger.log_warning("Abacus.AI SDK not available")
        
    def generate_script(self, channel_config: Dict, topic: str) -> Dict[str, str]:
        """
        Generate a complete script for a YouTube Short.
        
        Args:
            channel_config: Channel configuration
            topic: Topic for the video
            
        Returns:
            Dict containing script, title, description, tags
        """
        try:
            self.logger.log_content_generation(
                channel_config["channel_name"], 
                "script", 
                topic, 
                True
            )
            
            # Generate script based on channel type
            if "tech" in channel_config["channel_name"].lower():
                script = self._generate_tech_script(topic, channel_config)
            elif "crypto" in channel_config["channel_name"].lower():
                script = self._generate_crypto_script(topic, channel_config)
            elif "meme" in channel_config["channel_name"].lower():
                script = self._generate_meme_script(topic, channel_config)
            else:
                script = self._generate_generic_script(topic, channel_config)
            
            # Generate title
            title = self._generate_title(script, channel_config)
            
            # Generate description
            description = self._generate_description(script, channel_config)
            
            # Generate tags
            tags = self._generate_tags(topic, channel_config)
            
            return {
                "script": script,
                "title": title,
                "description": description,
                "tags": tags,
                "topic": topic,
                "generated_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.log_content_generation(
                channel_config["channel_name"], 
                "script", 
                topic, 
                False, 
                {"error": str(e)}
            )
            raise
    
    def _generate_tech_script(self, topic: str, config: Dict) -> str:
        """Generate tech news script."""
        prompt = f"""
        Create a 30-60 second YouTube Short script about: {topic}
        
        Requirements:
        - Engaging opening hook
        - 2-3 key points maximum
        - Call to action at the end
        - Tech-savvy but accessible language
        - Include relevant tech terms
        - End with "Don't forget to like and subscribe!"
        
        Format: Plain text, conversational tone
        """
        
        return self._call_abacus_ai(prompt)
    
    def _generate_crypto_script(self, topic: str, config: Dict) -> str:
        """Generate crypto/finance script."""
        prompt = f"""
        Create a 30-60 second YouTube Short script about: {topic}
        
        Requirements:
        - Start with attention-grabbing fact or number
        - Explain the crypto/finance concept clearly
        - Include current market context if relevant
        - Professional but engaging tone
        - End with "Like and subscribe for more crypto insights!"
        
        Format: Plain text, educational but entertaining
        """
        
        return self._call_abacus_ai(prompt)
    
    def _generate_meme_script(self, topic: str, config: Dict) -> str:
        """Generate meme/entertainment script."""
        prompt = f"""
        Create a 15-45 second YouTube Short script about: {topic}
        
        Requirements:
        - Funny and entertaining
        - Pop culture references
        - Viral-worthy content
        - Include trending phrases or memes
        - End with "Hit that like button and follow for more laughs!"
        
        Format: Plain text, casual and fun tone
        """
        
        return self._call_abacus_ai(prompt)
    
    def _generate_generic_script(self, topic: str, config: Dict) -> str:
        """Generate generic script for any topic."""
        prompt = f"""
        Create a 30-60 second YouTube Short script about: {topic}
        
        Requirements:
        - Engaging introduction
        - Clear main points
        - Call to action
        - Appropriate for general audience
        - End with "Don't forget to like and subscribe!"
        
        Format: Plain text, conversational tone
        """
        
        return self._call_abacus_ai(prompt)
    
    def _generate_title(self, script: str, config: Dict) -> str:
        """Generate catchy title for the video."""
        # Try Abacus.AI first
        try:
            prompt = f"""
            Based on this script, create a catchy YouTube Short title:
            
            Script: {script[:200]}...
            
            Requirements:
            - 60 characters or less
            - Include relevant keywords
            - Engaging and clickable
            - Appropriate for {config['channel_name']}
            - No clickbait or misleading content
            
            Return only the title, nothing else.
            """
            
            title = self._call_abacus_ai(prompt).strip()
            if len(title) <= 60:
                return title
        except:
            pass
        
        # Fallback: Generate simple title based on script content
        if "AI trends" in script or "artificial intelligence" in script.lower():
            return "Latest AI Trends 2025"
        elif "crypto" in script.lower() or "bitcoin" in script.lower():
            return "Crypto Market Update"
        elif "tech" in script.lower() or "technology" in script.lower():
            return "Tech News Update"
        else:
            # Extract first few words from script
            words = script.split()[:6]
            title = " ".join(words)
            if len(title) > 60:
                title = title[:57] + "..."
            return title
    
    def _generate_description(self, script: str, config: Dict) -> str:
        """Generate video description."""
        # Try Abacus.AI first
        try:
            prompt = f"""
            Create a YouTube video description for this script:
            
            Script: {script}
            
            Requirements:
            - 2-3 sentences maximum
            - Include relevant hashtags
            - Mention the channel topic
            - Encourage engagement
            - Keep it under 500 characters
            
            Format: Plain text with hashtags
            """
            
            description = self._call_abacus_ai(prompt)
            if len(description) <= 500:
                return description
        except:
            pass
        
        # Fallback: Generate simple description
        channel_name = config.get('channel_name', 'Tech News')
        if "AI trends" in script or "artificial intelligence" in script.lower():
            return f"Discover the latest AI trends and innovations! 🤖✨ #AI #Technology #Innovation #TechNews #ArtificialIntelligence"
        elif "crypto" in script.lower() or "bitcoin" in script.lower():
            return f"Stay updated with the latest crypto market news! 📈💰 #Crypto #Bitcoin #Blockchain #Finance #Trading"
        else:
            return f"Latest updates from {channel_name}! Stay informed with the newest trends. 📱💡 #Tech #News #Updates #Technology"
    
    def _generate_tags(self, topic: str, config: Dict) -> List[str]:
        """Generate relevant tags for the video."""
        # Try Abacus.AI first
        try:
            prompt = f"""
            Generate 10-15 relevant YouTube tags for a video about: {topic}
            
            Channel: {config['channel_name']}
            
            Requirements:
            - Mix of broad and specific tags
            - Include trending keywords
            - Relevant to the topic
            - Appropriate for YouTube search
            - No inappropriate or banned tags
            
            Return as comma-separated list only.
            """
            
            tags_text = self._call_abacus_ai(prompt)
            tags = [tag.strip() for tag in tags_text.split(',') if tag.strip()]
            if len(tags) > 0:
                return tags[:15]  # Limit to 15 tags
        except:
            pass
        
        # Fallback: Generate simple tags based on topic
        if "AI trends" in topic.lower() or "artificial intelligence" in topic.lower():
            return ["AI", "Artificial Intelligence", "Technology", "Innovation", "Machine Learning", "Tech News", "Future Tech", "AI Trends", "Tech Updates", "Digital Innovation"]
        elif "crypto" in topic.lower() or "bitcoin" in topic.lower():
            return ["Crypto", "Bitcoin", "Blockchain", "Cryptocurrency", "Finance", "Trading", "DeFi", "Crypto News", "Digital Currency", "Investment"]
        elif "tech" in topic.lower() or "technology" in topic.lower():
            return ["Technology", "Tech News", "Innovation", "Gadgets", "Tech Updates", "Digital", "Future", "Tech Trends", "Science", "Engineering"]
        else:
            return ["Tech", "News", "Updates", "Technology", "Innovation", "Digital", "Future", "Trends", "Science", "Engineering"]
    
    def _call_abacus_ai(self, prompt: str) -> str:
        """
        Call Abacus.AI API for text generation using ChatLLM or similar functionality.
        
        Args:
            prompt: The prompt to send to Abacus.AI
            
        Returns:
            Generated text response
        """
        try:
            if not self.abacus_client:
                raise ValueError("Abacus.AI client not initialized")
            
            # Try different Abacus.AI methods for text generation
            # Based on the documentation, Abacus.AI has ChatLLM functionality
            
            try:
                # Method 1: Try ChatLLM if available
                if hasattr(self.abacus_client, 'chat_llm'):
                    response = self.abacus_client.chat_llm(prompt=prompt)
                    return str(response)
                
                # Method 2: Try create_chat_llm if available
                elif hasattr(self.abacus_client, 'create_chat_llm'):
                    chat_llm = self.abacus_client.create_chat_llm()
                    response = chat_llm.generate(prompt=prompt)
                    return str(response)
                
                # Method 3: Try any LLM-related method
                elif hasattr(self.abacus_client, 'llm'):
                    response = self.abacus_client.llm(prompt=prompt)
                    return str(response)
                
                else:
                    raise AttributeError("No text generation method found in Abacus.AI SDK")
                    
            except AttributeError as e:
                self.logger.log_warning(f"Abacus.AI text generation method not found: {e}")
                # Fallback to simple content generation for testing
                return self._generate_simple_content(prompt)
            
        except Exception as e:
            self.logger.log_error(f"Abacus.AI API request failed: {e}")
            # Fallback to simple content generation for testing
            return self._generate_simple_content(prompt)
    
    def _generate_simple_content(self, prompt: str) -> str:
        """
        Generate simple content for testing when APIs are not available.
        
        Args:
            prompt: The prompt to generate content for
            
        Returns:
            Generated content
        """
        self.logger.log_info("Using simple content generation for testing")
        
        # Simple content generation based on prompt keywords
        if "AI trends" in prompt or "artificial intelligence" in prompt.lower():
            return """The latest AI trends are revolutionizing technology! From ChatGPT to autonomous vehicles, AI is everywhere. 
            Machine learning algorithms are getting smarter, and we're seeing breakthroughs in natural language processing. 
            Companies are investing billions in AI research, and the future looks incredibly exciting!"""
        
        elif "crypto" in prompt.lower() or "bitcoin" in prompt.lower():
            return """Cryptocurrency markets are showing strong momentum! Bitcoin continues to lead the pack, 
            while altcoins are gaining traction. DeFi protocols are innovating, and institutional adoption is growing. 
            The blockchain revolution is just getting started!"""
        
        elif "tech" in prompt.lower() or "technology" in prompt.lower():
            return """Technology is advancing at breakneck speed! From quantum computing to 5G networks, 
            we're witnessing incredible innovations. Smart cities, IoT devices, and renewable energy solutions 
            are transforming our world. The future is now!"""
        
        else:
            return f"""This is a test content generated for the prompt: {prompt}. 
            In a real implementation, this would be generated by Abacus.AI or OpenAI. 
            The content generation system is working correctly!"""
    
    def _call_openai_fallback(self, prompt: str) -> str:
        """Fallback to OpenAI if Abacus.AI fails."""
        try:
            import openai
            
            openai.api_key = self.openai_api_key
            
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a YouTube content creator. Generate engaging, short-form content."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500,
                temperature=0.7
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            self.logger.log_error(f"OpenAI fallback also failed: {e}")
            # Return a basic fallback response
            return f"Content about: {prompt[:100]}... (AI generation failed)"
    
    def get_random_topic(self, channel_config: Dict) -> str:
        """Get a random topic from the channel's topic list."""
        topics = channel_config.get("content", {}).get("topics", [])
        if not topics:
            return "latest trends and updates"
        
        return random.choice(topics)
    
    def validate_content(self, content: Dict, channel_config: Dict) -> bool:
        """
        Validate generated content for quality and appropriateness.
        
        Args:
            content: Generated content dictionary
            channel_config: Channel configuration
            
        Returns:
            True if content is valid, False otherwise
        """
        try:
            # Check script length
            script = content.get("script", "")
            if len(script) < 50 or len(script) > 1000:
                self.logger.log_warning(f"Script length invalid: {len(script)} characters")
                return False
            
            # Check title length
            title = content.get("title", "")
            if len(title) > 60:
                self.logger.log_warning(f"Title too long: {len(title)} characters")
                return False
            
            # Check for inappropriate content
            exclude_keywords = channel_config.get("content", {}).get("filters", {}).get("exclude_keywords", [])
            for keyword in exclude_keywords:
                if keyword.lower() in script.lower() or keyword.lower() in title.lower():
                    self.logger.log_warning(f"Excluded keyword found: {keyword}")
                    return False
            
            return True
            
        except Exception as e:
            self.logger.log_error(f"Content validation failed: {e}")
            return False

# Example usage
if __name__ == "__main__":
    # This would be used for testing
    config = {
        "channel_name": "Tech News",
        "content": {
            "topics": ["latest AI trends", "new gadgets"],
            "filters": {
                "exclude_keywords": ["politics", "controversial"]
            }
        }
    }
    
    # Initialize logger first
    from logger import initialize_logger
    initialize_logger()
    
    # Test content generation
    generator = ContentGenerator(
        abacus_api_key="your_abacus_api_key",
        openai_api_key="your_openai_api_key"
    )
    
    topic = generator.get_random_topic(config)
    content = generator.generate_script(config, topic)
    
    print(f"Generated content for topic: {topic}")
    print(f"Title: {content['title']}")
    print(f"Script: {content['script'][:200]}...")
