# OpenAI Integration Setup Guide

## Prerequisites

1. **OpenAI API Key**: Get your API key from [OpenAI Platform](https://platform.openai.com/api-keys)
2. **Credits**: Ensure you have credits in your OpenAI account for DALL-E 3 image generation

## Setup Instructions

### 1. Add OpenAI API Key to Environment

Add the following to your `.env` file in `/web_dashboard/backend/`:

```bash
# OpenAI Configuration
OPENAI_API_KEY=your-api-key-here
OPENAI_MODEL="dall-e-3"  # or "dall-e-2" for cheaper option
OPENAI_IMAGE_SIZE="1024x1024"  # Options: 1024x1024, 1024x1792, 1792x1024
OPENAI_IMAGE_QUALITY="standard"  # Options: standard, hd (hd is more expensive)
```

### 2. Verify Dependencies

The required dependencies are already in `requirements.txt`:
- `openai==1.12.0`
- `aiohttp==3.9.3`
- `asyncio-throttle==1.0.2`

### 3. Start the Backend

```bash
cd web_dashboard/backend
python app.py
```

## Using the Icon Generator

1. Navigate to the **Icons** tab in your dashboard
2. Click on the **Shopify** tab
3. You'll see all your Shopify collections
4. Click **"Generate Icon"** for any collection or **"Generate All Missing Icons"**

## How It Works

### Icon Generation Process

1. **Smart Prompting**: The system creates optimized prompts based on:
   - Collection name
   - Collection description
   - Product category type
   - Selected style (flat, outlined, filled, etc.)

2. **DALL-E 3 Generation**: 
   - Generates high-quality icons
   - Automatically downloads and stores locally
   - Handles rate limiting and retries

3. **Shopify Upload**:
   - Automatically uploads to Shopify
   - Updates collection image
   - Stores metadata about generation

### Pricing Estimates

- **DALL-E 3**: ~$0.040 per image (1024x1024 standard)
- **DALL-E 2**: ~$0.020 per image (1024x1024)

For 100 collections:
- DALL-E 3: ~$4.00
- DALL-E 2: ~$2.00

### Rate Limits

The system automatically handles OpenAI rate limits:
- Default: 50 requests per minute
- Configurable in the code if needed

## Customization Options

### Icon Styles

In the UI, you can select:
- **Flat**: Modern, minimalist design
- **Outlined**: Line art style
- **Filled**: Solid shapes with depth
- **Rounded**: Soft, friendly appearance
- **Sharp**: Professional, angular design

### Color Schemes
- **Monochrome**: Black and white
- **Brand**: Your brand colors
- **Category**: Auto-selected based on product type
- **Auto**: AI chooses appropriate colors

## Troubleshooting

### Common Issues

1. **"No API Key"**: Ensure `OPENAI_API_KEY` is set in `.env`
2. **"Rate Limit"**: Wait a minute or reduce batch size
3. **"Insufficient Credits"**: Add credits to your OpenAI account

### Testing

To test if OpenAI is configured correctly:

```bash
curl -X POST http://localhost:3560/api/icons/generate \
  -H "Content-Type: application/json" \
  -d '{
    "categories": ["test-category"],
    "config": {
      "style": "flat",
      "colorScheme": "brand",
      "size": "24",
      "format": "png"
    }
  }'
```

## Advanced Features

### Batch Processing

The system supports batch generation:
- Processes up to 10 icons concurrently
- Shows real-time progress
- Handles failures gracefully

### Caching

Generated icons are cached locally:
- Prevents duplicate API calls
- Allows for quick re-uploads
- Located in `data/category_icons/`

### Custom Prompts

The system uses intelligent prompt templates:
- Automatically adds relevant keywords
- Optimizes for icon generation
- Ensures consistent style

## Best Practices

1. **Start Small**: Test with a few collections first
2. **Review Generated Icons**: Check quality before bulk generation
3. **Use Consistent Styles**: Pick one style for all collections
4. **Monitor Costs**: Track usage in OpenAI dashboard

## Example Prompts Generated

For a collection named "Office Supplies":
```
Create a minimalist flat icon representing office supplies. 
The icon should be simple, recognizable, and work well at small sizes. 
Use a modern design style with clean lines. 
Primary color: #1e40af. 
Background: transparent.
```

The system automatically enhances prompts for better results!