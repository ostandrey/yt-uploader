# Technical Documentation - YouTube Automation Project

## 🏗️ Architecture Overview

### System Components
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Content       │    │   Visual        │    │   YouTube       │
│   Generator     │───▶│   Fetcher       │───▶│   Uploader      │
│                 │    │                 │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Abacus.AI     │    │   Stock APIs    │    │   OAuth 2.0     │
│   OpenAI        │    │   Pexels        │    │   Token Mgmt    │
│   Fallback      │    │   Pixabay       │    │   Video Upload  │
│                 │    │   Unsplash      │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 📁 Project Structure

```
yt-auto/
├── config/                 # Channel configurations
│   ├── tech_news.yaml     # Tech channel settings
│   ├── crypto_news.yaml   # Crypto channel settings
│   └── memes_channel.yaml # Memes channel settings
├── scripts/               # Core automation scripts
│   ├── main.py           # Main pipeline orchestrator
│   ├── generate_script.py # Content generation
│   ├── get_visuals.py    # Visual content fetching
│   ├── upload_youtube.py # YouTube integration
│   └── logger.py         # Logging and notifications
├── tests/                # Test suite
│   ├── test_auth.py      # Authentication tests
│   ├── test_content.py   # Content generation tests
│   └── test_tech_only.py # Complete pipeline test
├── credentials/          # OAuth credentials
│   ├── tech_credentials.json
│   ├── crypto_credentials.json
│   └── memes_credentials.json
├── tokens/              # OAuth tokens
│   └── tech_token.json
├── storage/             # Generated content storage
│   ├── tech_news/
│   ├── crypto_news/
│   └── memes_channel/
├── logs/                # Application logs
└── .env                 # Environment variables
```

## 🔧 Core Components

### 1. Content Generator (`scripts/generate_script.py`)

**Purpose**: Generate video content (scripts, titles, descriptions, tags)

**Key Features**:
- Abacus.AI integration with OpenAI fallback
- Channel-specific content generation
- Topic-based content creation
- Content validation and quality checks

**Methods**:
```python
class ContentGenerator:
    def __init__(self, abacus_api_key, openai_api_key=None)
    def generate_script(self, channel_config, topic)
    def _generate_tech_script(self, topic, channel_config)
    def _generate_crypto_script(self, topic, channel_config)
    def _generate_meme_script(self, topic, channel_config)
    def _call_abacus_ai(self, prompt)
    def _generate_simple_content(self, prompt)  # Fallback
```

**Content Types**:
- **Tech Channel**: AI trends, gadgets, tech news, startups
- **Crypto Channel**: Bitcoin, altcoins, DeFi, market analysis
- **Memes Channel**: Viral content, humor, entertainment

### 2. Visual Fetcher (`scripts/get_visuals.py`)

**Purpose**: Fetch visual content (images/videos) for videos

**Key Features**:
- Multiple stock media APIs (Pexels, Pixabay, Unsplash)
- AI-generated image fallback via Abacus.AI
- Keyword-based content matching
- Content relevance scoring

**Methods**:
```python
class VisualContentFetcher:
    def __init__(self, pexels_api_key, pixabay_api_key, unsplash_access_key, abacus_api_key)
    def get_visuals_for_script(self, content, channel_config, count=5)
    def _extract_keywords(self, script_text)
    def _fetch_stock_content(self, keywords, count)
    def _generate_ai_content(self, keywords, count)
    def _search_pexels(self, query, count)
    def _search_pixabay(self, query, count)
    def _search_unsplash(self, query, count)
```

**Visual Sources**:
- **Stock APIs**: Pexels, Pixabay, Unsplash
- **AI Generation**: Abacus.AI image generation
- **Fallback**: Simple placeholder images

### 3. YouTube Uploader (`scripts/upload_youtube.py`)

**Purpose**: Handle YouTube video uploads and channel management

**Key Features**:
- OAuth 2.0 authentication
- Token management and refresh
- Video upload with metadata
- Channel information retrieval

**Methods**:
```python
class YouTubeUploader:
    def __init__(self, channel_name, credentials_file, token_file)
    def _authenticate(self)
    def upload_video(self, video_path, title, description, tags, privacy_status="unlisted")
    def update_video_status(self, video_id, privacy_status)
    def get_channel_info(self)
    def delete_video(self, video_id)

class YouTubeManager:
    def __init__(self, config)
    def _initialize_uploaders(self)
    def get_uploader(self, channel_key)
    def upload_to_channel(self, channel_key, video_path, metadata)
```

### 4. Logger System (`scripts/logger.py`)

**Purpose**: Comprehensive logging and notification system

**Key Features**:
- File logging with rotation
- Telegram notifications
- Error tracking and reporting
- Performance monitoring

**Methods**:
```python
class YouTubeAutomationLogger:
    def __init__(self, log_level="INFO", telegram_token=None, telegram_chat_id=None)
    def log_info(self, message, channel=None)
    def log_warning(self, message, channel=None)
    def log_error(self, message, channel=None, error_details=None)
    def log_success(self, message, channel=None)
    def send_telegram_notification(self, message)
    def log_video_creation(self, channel, topic, video_path, duration, status)
    def log_upload_attempt(self, channel, video_path, youtube_id=None, status="attempted")
    def log_daily_summary(self, summary)
```

## 🔐 Authentication & Security

### YouTube OAuth 2.0
- **Credentials**: Stored in `credentials/` directory
- **Tokens**: Stored in `tokens/` directory
- **Scopes**: `https://www.googleapis.com/auth/youtube.upload`
- **Refresh**: Automatic token refresh

### API Keys
- **Abacus.AI**: Content generation
- **OpenAI**: Fallback content generation
- **Stock Media**: Pexels, Pixabay, Unsplash
- **Telegram**: Notifications

### Security Measures
- Environment variables for sensitive data
- `.gitignore` for credentials and tokens
- Secure token storage
- API key rotation support

## 📊 Data Flow

### 1. Content Generation Flow
```
Topic Selection → Content Generation → Validation → Output
     ↓                    ↓                ↓         ↓
Random/Manual → Abacus.AI/OpenAI → Quality Check → Script+Metadata
```

### 2. Visual Fetching Flow
```
Script Analysis → Keyword Extraction → API Search → Content Selection
     ↓                    ↓                ↓            ↓
Content Text → NLP Processing → Stock APIs → Relevance Scoring
```

### 3. Video Creation Flow
```
Content + Visuals → Video Assembly → Quality Check → Upload
     ↓                    ↓              ↓           ↓
Script+Images → MoviePy/FFmpeg → Validation → YouTube API
```

## 🧪 Testing Strategy

### Test Categories
1. **Unit Tests**: Individual component testing
2. **Integration Tests**: Component interaction testing
3. **End-to-End Tests**: Complete pipeline testing
4. **API Tests**: External service integration testing

### Test Files
- `test_auth.py`: YouTube authentication testing
- `test_content.py`: Content generation testing
- `test_tech_only.py`: Complete Tech channel pipeline testing

### Test Coverage
- ✅ Authentication flows
- ✅ Content generation
- ✅ Visual fetching
- ✅ YouTube integration
- ✅ Error handling
- ✅ Logging and notifications

## 🚀 Deployment & Scaling

### Local Development
- Conda environment management
- Local file storage
- Development logging

### Production Deployment
- Docker containerization
- Cloud storage (MinIO/S3)
- Scheduled execution
- Monitoring and alerting

### Scaling Considerations
- Multi-channel support
- Queue-based processing
- Load balancing
- Resource optimization

## 📈 Performance Metrics

### Current Performance
- **Content Generation**: ~2-3 seconds
- **Visual Fetching**: ~5-10 seconds
- **Video Assembly**: ~30-60 seconds
- **YouTube Upload**: ~1-2 minutes

### Optimization Opportunities
- Parallel processing
- Caching mechanisms
- API rate limiting
- Resource pooling

## 🔧 Configuration Management

### Channel Configuration (`config/*.yaml`)
```yaml
channel_name: "Tech News"
settings:
  visual_source: "mixed"
  voiceover: true
  voice: "Aria"
  music: "neutral_background"
  schedule: "2_per_day"
  video_duration: "30-60"
  quality_check: true
  auto_upload: false

content:
  topics: ["latest AI trends", "new gadgets", ...]
  sources: ["tech_crunch", "the_verge", ...]
  filters:
    min_engagement: 100
    exclude_keywords: ["politics", "controversial"]
    preferred_keywords: ["AI", "technology", "innovation"]
```

### Environment Configuration (`.env`)
```env
# YouTube API Configuration
YOUTUBE_TECH_API_KEY=your_api_key
YOUTUBE_TECH_CLIENT_ID=your_client_id
YOUTUBE_TECH_CLIENT_SECRET=your_client_secret

# Abacus.AI Configuration
ABACUS_API_KEY=your_abacus_key

# Stock Media APIs
PEXELS_API_KEY=your_pexels_key
PIXABAY_API_KEY=your_pixabay_key
UNSPLASH_ACCESS_KEY=your_unsplash_key

# Telegram Bot
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

## 🐛 Error Handling & Recovery

### Error Categories
1. **API Errors**: Rate limiting, authentication failures
2. **Content Errors**: Generation failures, validation errors
3. **Upload Errors**: YouTube API issues, network problems
4. **System Errors**: File system, memory, disk space

### Recovery Mechanisms
- Automatic retries with exponential backoff
- Fallback content generation
- Alternative visual sources
- Manual intervention alerts

### Monitoring & Alerting
- Telegram notifications for critical errors
- Daily summary reports
- Performance metrics tracking
- Error rate monitoring
