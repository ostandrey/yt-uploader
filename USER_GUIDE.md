# User Guide - YouTube Automation Project

## 🚀 Quick Start

### Prerequisites
- Python 3.12+
- Conda package manager
- Google Cloud Console account
- Abacus.AI account
- Stock media API accounts (Pexels, Pixabay, Unsplash)

### Installation
```bash
# Clone the repository
git clone <repository-url>
cd yt-auto

# Create conda environment
conda create -n yt-auto-uploader python=3.12 -y
conda activate yt-auto-uploader

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp env_example.txt .env
# Edit .env with your API keys
```

## 🎬 Creating Your First Automated Video

### Step 1: Test the Pipeline
```bash
cd tests
python test_tech_only.py
```

**Expected Output**:
```
✅ Logger initialized
✅ Content generator initialized
✅ Visual fetcher initialized
✅ YouTube uploader initialized
✅ Content generated successfully
✅ Visuals fetched: 5 items
🎉 Tech channel pipeline test successful!
```

### Step 2: Create and Upload a Video
```bash
cd ..
python scripts/main.py --channel tech_news --topic "latest AI trends"
```

### Step 3: Monitor Progress
- Check Telegram notifications
- Review logs in `logs/` directory
- Verify video upload in YouTube Studio

## 📺 Channel Management

### Tech Channel
- **Focus**: Technology news, AI trends, gadgets
- **Content**: 10 predefined topics
- **Schedule**: 2 videos per day
- **Duration**: 30-60 seconds (Shorts)

### Crypto Channel (Planned)
- **Focus**: Cryptocurrency news, market analysis
- **Content**: Bitcoin, altcoins, DeFi
- **Schedule**: 2 videos per day
- **Duration**: 30-60 seconds (Shorts)

### Memes Channel (Planned)
- **Focus**: Viral content, humor, entertainment
- **Content**: Trending memes, funny videos
- **Schedule**: 2 videos per day
- **Duration**: 30-60 seconds (Shorts)

## ⚙️ Configuration

### Channel Settings
Edit `config/tech_news.yaml`:
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
  auto_upload: false        # Start with manual approval
```

### Environment Variables
Edit `.env` file:
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

## 🔄 Automation Workflow

### Daily Automation
1. **Content Generation**: Create script for selected topic
2. **Visual Fetching**: Get relevant images/videos
3. **Video Assembly**: Combine content and visuals
4. **Quality Check**: Validate video quality
5. **Upload**: Upload to YouTube (Unlisted initially)
6. **Notification**: Send status to Telegram

### Manual Override
- Review videos before publishing
- Edit titles/descriptions if needed
- Change privacy status (Unlisted → Public)
- Delete videos if not satisfied

## 📊 Monitoring & Analytics

### Telegram Notifications
- ✅ Success notifications
- ❌ Error alerts
- 📊 Daily summaries
- 🔄 Status updates

### Log Files
- `logs/app_YYYYMMDD.log`: Daily application logs
- `logs/videos_YYYYMMDD.log`: Video creation logs
- Error tracking and debugging information

### YouTube Analytics
- Monitor video performance
- Track engagement metrics
- Analyze audience growth
- Optimize content strategy

## 🛠️ Troubleshooting

### Common Issues

#### 1. Authentication Errors
**Problem**: `403: access_denied`
**Solution**: 
- Check OAuth consent screen configuration
- Verify test users are added
- Ensure API keys are correct

#### 2. Content Generation Failures
**Problem**: No content generated
**Solution**:
- Check Abacus.AI API key
- Verify OpenAI fallback key
- Review topic configuration

#### 3. Visual Fetching Issues
**Problem**: No visuals found
**Solution**:
- Check stock media API keys
- Verify internet connection
- Review keyword extraction

#### 4. Upload Failures
**Problem**: Video upload fails
**Solution**:
- Check YouTube API quota
- Verify video file format
- Review upload permissions

### Debug Mode
Enable detailed logging:
```bash
export LOG_LEVEL=DEBUG
python scripts/main.py
```

### Manual Testing
Test individual components:
```bash
# Test authentication
python tests/test_auth.py

# Test content generation
python tests/test_content.py

# Test complete pipeline
python tests/test_tech_only.py
```

## 📈 Scaling & Optimization

### Adding New Channels
1. Create channel configuration in `config/`
2. Set up OAuth credentials
3. Add channel to YouTubeManager
4. Test channel-specific pipeline

### Performance Optimization
- Use parallel processing for multiple channels
- Implement caching for API responses
- Optimize video rendering settings
- Monitor resource usage

### Content Strategy
- Analyze successful videos
- Adjust topic selection
- Optimize visual content
- Improve engagement metrics

## 🔒 Security Best Practices

### API Key Management
- Store keys in environment variables
- Never commit keys to version control
- Rotate keys regularly
- Use least-privilege access

### Data Protection
- Secure token storage
- Encrypt sensitive data
- Regular backups
- Access logging

### YouTube Compliance
- Follow YouTube policies
- Respect copyright laws
- Monitor content quality
- Handle strikes appropriately

## 📞 Support & Maintenance

### Regular Maintenance
- Update dependencies monthly
- Review and rotate API keys
- Monitor error rates
- Optimize performance

### Backup Strategy
- Regular configuration backups
- Token file backups
- Log file archiving
- Disaster recovery plan

### Community Support
- GitHub issues for bug reports
- Documentation updates
- Feature requests
- Community contributions

## 🎯 Success Metrics

### Key Performance Indicators
- **Automation Success Rate**: >95%
- **Video Quality Score**: >8/10
- **Upload Success Rate**: >98%
- **Error Resolution Time**: <1 hour

### Growth Metrics
- **Channel Subscribers**: Monthly growth
- **Video Views**: Engagement tracking
- **Revenue**: Monetization progress
- **Efficiency**: Time saved vs manual creation

## 🚀 Future Enhancements

### Phase 2: Dynamic Content
- RSS feed integration
- Social media monitoring
- Google Trends integration
- Real-time news analysis

### Phase 3: AI Optimization
- Content personalization
- Audience targeting
- Performance prediction
- Automated optimization

### Phase 4: Advanced Features
- Multi-language support
- Voice synthesis
- Advanced video effects
- Cross-platform publishing
