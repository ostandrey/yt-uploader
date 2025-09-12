# YouTube Automation Project

Automated YouTube Shorts generation and publishing system using AI and Python.

## 🎯 Project Overview

This project automates the creation and publishing of YouTube Shorts across multiple channels:
- **Tech News** - Technology and AI news
- **Crypto/Finance News** - Cryptocurrencies, finance, investments  
- **Meme/Entertainment** - Memes, humor, entertainment content

## 🚀 Features

- **AI-powered content generation** using Abacus.AI
- **Automated video creation** with voiceover and visuals
- **Multi-channel management** with different content strategies
- **Smart content sourcing** (stock photos + AI generation)
- **Automated publishing** with quality control
- **Real-time monitoring** via Telegram notifications
- **Scalable architecture** for easy expansion

## 📋 Prerequisites

### Required Accounts & API Keys

1. **YouTube/Google Cloud**
   - Google Cloud Console account
   - YouTube Data API v3 enabled
   - API credentials created

2. **Abacus.AI**
   - Active subscription
   - API access configured

3. **Stock Content APIs**
   - Pexels API key
   - Pixabay API key
   - Unsplash API key

4. **Telegram Bot**
   - Bot created via @BotFather
   - Bot token and chat ID

5. **Storage** (Optional for start)
   - Local storage (default)
   - MinIO/S3 for scaling

## 🛠 Installation

### 1. Clone Repository
```bash
git clone <repository-url>
cd youtube_automation_project
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure Environment
```bash
# Copy example environment file
cp env_example.txt .env

# Edit .env with your API keys
nano .env
```

### 4. Set Up Configuration Files
```bash
# Configure your channels
cp config/channel_template.yaml config/tech_news.yaml
cp config/channel_template.yaml config/crypto_news.yaml
cp config/channel_template.yaml config/memes_channel.yaml
```

## 📁 Project Structure

```
youtube_automation_project/
├── config/                 # Channel configurations
│   ├── tech_news.yaml
│   ├── crypto_news.yaml
│   └── memes_channel.yaml
├── scripts/               # Core automation scripts
│   ├── main.py           # Main pipeline
│   ├── generate_script.py # Content generation
│   ├── get_visuals.py    # Stock content fetching
│   ├── generate_audio.py # Voiceover generation
│   ├── assemble_video.py # Video assembly
│   ├── upload_youtube.py # YouTube upload
│   └── logger.py         # Logging and notifications
├── storage/              # Generated content storage
│   ├── tech_news/
│   ├── crypto_news/
│   └── memes_channel/
├── logs/                 # Application logs
├── .env                  # Environment variables
├── requirements.txt      # Python dependencies
└── README.md            # This file
```

## ⚙️ Configuration

### Channel Configuration Example
```yaml
channel_name: "Tech News"
settings:
  visual_source: "mixed"    # stock / generated / mixed
  voiceover: true
  voice: "Aria"
  music: "neutral_background"
  schedule: "2_per_day"
  video_duration: "30-60"
  quality_check: true

content:
  topics:
    - "latest AI trends"
    - "new gadgets"
    - "big tech news"
  sources:
    - "rss_feeds"
    - "twitter_trends"
    - "reddit_hot"
```

## 🎬 Usage

### Start the Automation
```bash
python scripts/main.py
```

### Manual Content Generation
```bash
python scripts/generate_script.py --channel tech_news --topic "AI breakthrough"
```

### Check Logs
```bash
tail -f logs/app.log
```

## 🔧 Development

### Adding New Channels
1. Create new config file in `config/`
2. Add channel settings
3. Update main.py to include new channel

### Customizing Content Generation
- Modify `scripts/generate_script.py` for different content styles
- Update `scripts/get_visuals.py` for different visual sources
- Adjust `scripts/assemble_video.py` for different video formats

## 📊 Monitoring

### Telegram Notifications
- Success/failure notifications
- Daily reports
- Error alerts

### Log Files
- Detailed operation logs
- Error tracking
- Performance metrics

## 🚀 Scaling

### Local Development
- Start with local storage
- Single machine deployment
- Manual quality control

### Production Deployment
- VPS/Cloud hosting
- MinIO/S3 storage
- Docker containers
- Automated quality checks

## 🔒 Security

- API keys stored in `.env` file
- Never commit sensitive data
- Use environment variables
- Regular security updates

## 📈 Performance

### Current Capabilities
- 6 Shorts per day (2 per channel)
- 30-60 second videos
- Mixed content sources
- Automated publishing

### Future Enhancements
- Increased daily output
- More channels
- Advanced analytics
- A/B testing

## 🤝 Contributing

1. Fork the repository
2. Create feature branch
3. Make changes
4. Test thoroughly
5. Submit pull request

## 📄 License

This project is licensed under the MIT License.

## 🆘 Support

For issues and questions:
- Check logs in `logs/` directory
- Review configuration files
- Check API key validity
- Contact support team

## 🔄 Updates

- Regular dependency updates
- New feature additions
- Bug fixes and improvements
- Performance optimizations

