# Deployment Guide - Render.com

This guide walks through deploying the RAG Safety Checker API to Render.com's free tier.

## Prerequisites

- GitHub account with this repository pushed
- Render.com account (free tier)
- Environment variable values:
  - `SUPABASE_URL`
  - `SUPABASE_KEY`
  - `GROQ_API_KEY`

## Deployment Steps

### 1. Prepare Repository

Ensure your repository is pushed to GitHub with all latest changes:

```bash
git add .
git commit -m "feat(deployment): prepare for Render deployment"
git push origin main
```

### 2. Create Render Account

1. Go to https://render.com
2. Sign up with GitHub (recommended for easy integration)
3. Authorize Render to access your repositories

### 3. Deploy Using render.yaml (Recommended)

The repository includes a `render.yaml` Blueprint that automates deployment:

1. Go to Render Dashboard: https://dashboard.render.com
2. Click **"New +"** → **"Blueprint"**
3. Connect your GitHub repository
4. Select the repository: `risk_analysis_RAG`
5. Render will detect `render.yaml` automatically
6. Click **"Apply"**

### 4. Configure Environment Variables

After Blueprint creation, add the required secret values:

1. Go to your service: **rag-safety-checker**
2. Navigate to **"Environment"** tab
3. Add the following secret values:
   - `SUPABASE_URL`: Your Supabase project URL
   - `SUPABASE_KEY`: Your Supabase anon/public key
   - `GROQ_API_KEY`: Your Groq API key from https://console.groq.com/keys

The following are already configured in `render.yaml`:
- `LLM_PROVIDER=groq`
- `LLM_MODEL=llama-3.3-70b-versatile`
- `PYTHONUNBUFFERED=1`
- `LOG_LEVEL=INFO`
- `CACHE_TTL_DEFAULT=7`

4. Click **"Save Changes"**
5. Render will automatically redeploy with new environment variables

### 5. Manual Deployment (Alternative)

If you prefer manual setup instead of Blueprint:

1. Click **"New +"** → **"Web Service"**
2. Connect your GitHub repository
3. Configure:
   - **Name**: `rag-safety-checker`
   - **Region**: Oregon (or closest to you)
   - **Branch**: `main`
   - **Environment**: `Docker`
   - **Dockerfile Path**: `./Dockerfile`
   - **Docker Context**: `.`
   - **Instance Type**: `Free`
4. Add environment variables (see step 4 above)
5. Click **"Create Web Service"**

### 6. Verify Deployment

Once deployed, Render provides a public URL: `https://rag-safety-checker.onrender.com`

Test the endpoints:

```bash
# Health check
curl https://rag-safety-checker.onrender.com/health

# API info
curl https://rag-safety-checker.onrender.com/

# Safety check (example)
curl -X POST https://rag-safety-checker.onrender.com/safety-check \
  -H "Content-Type: application/json" \
  -d '{
    "ticker": "AAPL",
    "allocation_pct": 15.0
  }'
```

Expected responses:
- Health: `{"status": "healthy", "timestamp": "...", "dependencies": {...}}`
- Root: `{"name": "RAG Safety Checker API", "version": "1.0.0", ...}`
- Safety check: `{"decision": "PROCEED|REDUCE|VETO", ...}`

## Deployment Configuration

### render.yaml Structure

```yaml
services:
  - type: web
    name: rag-safety-checker
    env: docker
    region: oregon
    plan: free
    dockerfilePath: ./Dockerfile
    dockerContext: .
    healthCheckPath: /health
    envVars:
      - key: SUPABASE_URL
        sync: false
      - key: SUPABASE_KEY
        sync: false
      - key: GROQ_API_KEY
        sync: false
      - key: LLM_PROVIDER
        value: "groq"
      - key: LLM_MODEL
        value: "llama-3.3-70b-versatile"
      - key: PYTHONUNBUFFERED
        value: "1"
      - key: LOG_LEVEL
        value: "INFO"
      - key: CACHE_TTL_DEFAULT
        value: "7"
```

### Dockerfile Configuration

The Dockerfile is optimized for production:
- Uses Python 3.11 slim base image
- Installs PyTorch CPU-only version (smaller footprint)
- Uses `--no-cache-dir` to reduce image size
- Supports dynamic port via `$PORT` environment variable
- Sets `PYTHONUNBUFFERED=1` for proper logging

## Free Tier Limitations

Render's free tier has the following constraints:

1. **Cold Starts**: Service sleeps after 15 minutes of inactivity
   - First request after sleep takes 30-60 seconds
   - Subsequent requests are fast (<5 seconds)

2. **Build Time**: ~5-10 minutes for initial build
   - PyTorch installation takes the longest
   - Subsequent builds use cache when possible

3. **Memory**: 512 MB RAM
   - Sufficient for this application
   - Model embeddings are loaded lazily

4. **Bandwidth**: 100 GB/month
   - More than enough for typical usage

5. **Build Minutes**: 500 minutes/month
   - Each deployment counts toward this limit

## Monitoring

### View Logs

1. Go to your service dashboard
2. Click **"Logs"** tab
3. View real-time application logs

### Check Metrics

1. Click **"Metrics"** tab
2. Monitor:
   - Response times
   - Memory usage
   - CPU usage
   - Request count

### Health Checks

Render automatically pings `/health` endpoint every 30 seconds:
- If unhealthy, service is restarted automatically
- View health check history in dashboard

## Troubleshooting

### Service Won't Start

1. Check logs for errors
2. Verify all environment variables are set
3. Ensure Supabase credentials are correct
4. Check Groq API key is valid

### Slow Response Times

1. First request after cold start is slow (expected)
2. Keep service warm with periodic pings:
   ```bash
   # Cron job to ping every 10 minutes
   */10 * * * * curl https://rag-safety-checker.onrender.com/health
   ```

### Build Failures

1. Check Dockerfile syntax
2. Verify requirements.txt is valid
3. Review build logs in Render dashboard
4. Ensure PyTorch installation succeeds

### Database Connection Issues

1. Verify Supabase URL and key
2. Check Supabase project is active
3. Ensure database tables exist (run migrations)
4. Test connection from local environment first

## Updating Deployment

### Automatic Deploys

Render automatically deploys when you push to GitHub:

```bash
git add .
git commit -m "feat: add new feature"
git push origin main
```

Render detects the push and rebuilds/redeploys automatically.

### Manual Deploy

1. Go to service dashboard
2. Click **"Manual Deploy"** → **"Deploy latest commit"**
3. Select branch and click **"Deploy"**

### Rollback

1. Go to **"Events"** tab
2. Find previous successful deploy
3. Click **"Rollback to this version"**

## Cost Optimization

Free tier is sufficient for development and testing. For production:

1. **Upgrade to Starter ($7/month)**:
   - No cold starts
   - 512 MB RAM (same as free)
   - Faster builds

2. **Use Caching Effectively**:
   - Cache TTL is set to 7 days
   - Reduces database queries
   - Improves response times

3. **Monitor LLM Usage**:
   - Groq is free but rate-limited
   - Consider caching LLM responses
   - Current usage: ~$0/month (free tier)

## Security Best Practices

1. **Never commit secrets**:
   - Use Render environment variables
   - Keep `.env` in `.gitignore`

2. **Rotate API keys regularly**:
   - Update in Render dashboard
   - Service auto-redeploys with new keys

3. **Use HTTPS only**:
   - Render provides SSL certificates automatically
   - All traffic is encrypted

4. **Monitor access logs**:
   - Review logs for suspicious activity
   - Set up alerts for errors

## Next Steps

After successful deployment:

1. Test all API endpoints
2. Verify cache behavior
3. Monitor performance metrics
4. Set up uptime monitoring (e.g., UptimeRobot)
5. Document API URL for frontend integration

## Support

- Render Documentation: https://render.com/docs
- Render Community: https://community.render.com
- Project Issues: GitHub repository issues tab
