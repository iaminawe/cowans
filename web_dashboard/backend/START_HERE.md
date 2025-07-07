# 🚀 START HERE - Cowan's Product Dashboard

## Quick Start (One Command!)

To start the dashboard, simply run:

```bash
./start_dashboard.sh
```

That's it! The script will:
- ✅ Set up everything automatically
- ✅ Install all dependencies
- ✅ Initialize the database
- ✅ Start the web server

## Access the Dashboard

Once started, open your browser to:
- 🌐 **Dashboard**: http://localhost:5000
- 📊 **API**: http://localhost:5000/api

## First Time Setup?

The startup script handles everything, but if you need to configure:

1. **Environment Variables**: Edit the `.env` file in the project root
2. **Database**: Automatically created as `database.db`
3. **Logs**: Check `logs/` directory for any issues

## Common Commands

```bash
# Start the dashboard
./start_dashboard.sh

# Run tests
pytest

# Check logs
tail -f logs/app.log
```

## Need Help?

- Check the full documentation in `README.md`
- Review logs in the `logs/` directory
- Ensure port 5000 is not in use

---

**Remember: Just run `./start_dashboard.sh` to get started!**