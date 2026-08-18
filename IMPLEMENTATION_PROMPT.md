# AI Prompt: Fix All Code Review Issues - Paradox Discord Bot

## COMPREHENSIVE FIX PROMPT

You are a senior Python developer tasked with refactoring and improving the Paradox Discord Bot to production-grade quality. The bot searches Paradox game wikis and redirects users to relevant wiki pages.

### SCOPE OF WORK

Fix ALL identified issues from the code review:

1. **Architecture & Structure** - Refactor monolithic main.py into modular structure
2. **Error Handling** - Add comprehensive try-except blocks throughout
3. **Logging** - Replace all print() statements with proper logging
4. **Configuration** - Centralize all hardcoded values
5. **Database** - Implement proper database manager with validation
6. **Input Validation** - Add query validation and sanitization
7. **Async/Await** - Fix blocking operations in async contexts
8. **Security** - Fix path traversal vulnerabilities
9. **Type Hints** - Add complete type hints throughout
10. **Dependencies** - Fix requirements.txt and add missing packages

### CURRENT PROJECT STRUCTURE
```
Paradox-Discord-Bot/
├── main.py (310 lines - everything mixed together)
├── requirements.txt (incomplete)
├── pyproject.toml
├── .env.example (missing)
├── .gitignore
├── .replit
└── databases/ (game SQLite files)
```

### TARGET PROJECT STRUCTURE
```
Paradox-Discord-Bot/
├── src/
│   ├── __init__.py
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.py (Pydantic configuration)
│   ├── database/
│   │   ├── __init__.py
│   │   └── manager.py (Database abstraction)
│   ├── bot/
│   │   ├── __init__.py
│   │   ├── client.py (Bot initialization)
│   │   └── cogs/
│   │       ├── __init__.py
│   │       ├── wiki.py (Wiki search commands)
│   │       └── admin.py (Admin utilities)
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── logger.py (Logging configuration)
│   │   ├── validators.py (Input validation)
│   │   ├── cache.py (Search caching)
│   │   └── rate_limiter.py (Rate limiting)
│   └── api/
│       ├── __init__.py
│       └── server.py (Flask health check API)
├── main.py (Clean entry point)
├── requirements.txt (Complete, updated)
├── requirements-dev.txt (Development dependencies)
├── .env.example (Configuration template)
├── .gitignore (Updated)
├── pytest.ini (Test configuration)
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── unit/
    │   ├── test_validators.py
    │   ├── test_database.py
    │   └── test_cache.py
    └── integration/
        └── test_bot_commands.py
```

### DETAILED IMPLEMENTATION REQUIREMENTS

#### 1. CREATE config/settings.py
```python
# Use Pydantic v2 BaseSettings for type-safe configuration
# Define GameConfig dataclass with: name, color, logo_url, wiki_base_url
# Define Settings class with all environment variables:
#   - DISCORD_TOKEN (required, from .env)
#   - LOG_CHANNEL_ID (required, from .env)
#   - DB_DIR (default: "databases")
#   - BOT_PREFIX (default: "-")
#   - SERVER_HOST (default: "0.0.0.0")
#   - SERVER_PORT (default: 8080)
#   - MAX_QUERY_LENGTH (default: 100)
#   - SEARCH_RESULT_LIMIT (default: 7)
#   - MAX_BUTTONS (default: 5)
#   - All 6 games (eu4, hoi4, stl, imp, vic3, ck3)
# Load from .env file automatically
# Validate that required fields are set
```

#### 2. CREATE utils/logger.py
```python
# Setup structured logging
# Replace all print() statements
# Create logger function that:
#   - Outputs to console (INFO level)
#   - Outputs to logs/bot.log (DEBUG level with rotation)
#   - Includes timestamp, level, module, function, line number
# Handle exceptions with full traceback
```

#### 3. CREATE utils/validators.py
```python
# QueryValidator class:
#   - validate() method that checks:
#     * Query is not empty
#     * Query length <= MAX_QUERY_LENGTH
#     * Query contains only safe characters
#   - Raise ValueError with clear messages
# 
# GameKeyValidator class:
#   - validate_game_key() that:
#     * Checks key is alphanumeric
#     * Checks key length <= 10
#     * Checks key exists in configured games
#   - Prevent path traversal attacks
# 
# FilenameValidator class:
#   - sanitize_filename() that:
#     * Removes/replaces unsafe characters
#     * Prevents directory traversal
#     * Returns safe filename or default
```

#### 4. CREATE database/manager.py
```python
# DatabaseManager class:
#   - Constructor takes db_dir parameter
#   - get_db_path(game_key) returns validated path
#   - search_pages(game_key, query, limit) returns List[Dict]
#     * Check cache first
#     * Query database with timeout=5.0
#     * Use sqlite3.Row for named columns
#     * Handle sqlite3.Error exceptions
#     * Log all operations
#   - log_upload(user_id, filename, url) for PDX Tools uploads
#   - All methods have complete type hints and docstrings
#   - All database operations wrapped in try-except
#   - Use context managers for connections
```

#### 5. CREATE utils/cache.py
```python
# SearchCache class:
#   - Constructor with ttl_seconds parameter
#   - get(game_key, query) returns Optional[List]
#   - set(game_key, query, results) stores results
#   - invalidate(game_key=None) clears cache
#   - generate_key() uses MD5 hash of "game_key:query"
#   - Auto-expire entries after TTL
#   - get_stats() returns cache statistics
```

#### 6. CREATE utils/rate_limiter.py
```python
# RateLimiter class:
#   - Constructor with max_requests and window_seconds
#   - is_allowed(user_id) returns bool
#   - get_remaining(user_id) returns int
#   - Clean old requests automatically
#   - Store user request timestamps
```

#### 7. CREATE bot/client.py
```python
# DiscordBot class:
#   - Constructor takes config
#   - Initialize bot with Intents
#   - Load all cogs from cogs/
#   - Setup event handlers (on_ready, on_error)
#   - start() method runs bot
# 
# Initialize dependencies:
#   - DatabaseManager
#   - SearchCache
#   - RateLimiter
#   - Logger
#   - Pass to cogs as dependencies
```

#### 8. CREATE bot/cogs/wiki.py
```python
# WikiCog class(commands.Cog):
#   - __init__(bot, db, cache, rate_limiter)
#   - help() command - show all game commands
#   - search_and_display(game_key, query) - core logic
#     * Check rate limiter
#     * Validate query
#     * Search with timeout
#     * Send results or no-results message
#     * Log search
#     * Handle all exceptions
#   - send_results_embed() - format Discord embed
#   - send_no_results_embed() - no results message
#   - log_search() - log to Discord channel
# 
# Register game commands dynamically:
#   - For each game in config.games
#   - Create command that calls search_and_display
#   - All with proper error handling
# 
# tools() command - PDX.tools integration:
#   - Async file handling with aiofiles
#   - Proper error messages
#   - Database logging
#   - Input validation
```

#### 9. CREATE bot/cogs/admin.py
```python
# AdminCog class(commands.Cog):
#   - @commands.is_owner() decorator
#   - cache_clear() - clear search cache
#   - cache_stats() - show cache statistics
#   - db_stats() - show database statistics
```

#### 10. CREATE api/server.py
```python
# Create Flask app with:
#   - GET /health - returns {"status": "healthy", "timestamp": ISO}
#   - GET /health/ready - checks if bot is connected
#   - GET /stats/cache - returns cache statistics
#   - Proper error handlers (404, 500)
#   - CORS enabled
# 
# APIServer class:
#   - run_async() method to start in async context
#   - Graceful shutdown handling
#   - Logging for all requests
```

#### 11. UPDATE main.py
```python
# Clean entry point:
# 
# if __name__ == '__main__':
#     settings = Settings()
#     bot = DiscordBot(settings)
#     asyncio.run(bot.start())
# 
# Keep it simple and minimal
```

#### 12. CREATE .env.example
```
DISCORD_TOKEN=your_bot_token_here
LOG_CHANNEL_ID=123456789012345678
DB_DIR=databases
BOT_PREFIX=-
SERVER_PORT=8080
MAX_QUERY_LENGTH=100
SEARCH_RESULT_LIMIT=7
```

#### 13. UPDATE requirements.txt
```
discord.py==2.3.2
python-dotenv==1.0.0
flask==3.0.0
pydantic==2.0.0
pydantic-settings==2.0.0
aiofiles==23.2.1
```

#### 14. CREATE requirements-dev.txt
```
-r requirements.txt
pytest==7.4.0
pytest-asyncio==0.21.0
pytest-cov==4.1.0
black==23.9.1
pylint==2.17.5
mypy==1.5.1
```

#### 15. ADD COMPREHENSIVE ERROR HANDLING
```python
# Every async function should have try-except:
#   - sqlite3.Error for database operations
#   - discord.DiscordException for Discord API
#   - asyncio.TimeoutError for timeouts
#   - ValueError for validation
#   - Generic Exception as fallback
# 
# Log errors with full context
# Send user-friendly error messages
# Never expose stack traces to users
```

#### 16. ADD COMPLETE TYPE HINTS
```python
# All functions must have:
#   - Parameter types (including Optional, List, Dict, etc.)
#   - Return types
#   - Docstrings with Args, Returns, Raises
# 
# Example:
# async def search_pages(
#     self,
#     game_key: str,
#     query: str,
#     limit: int = 10
# ) -> List[Dict[str, str]]:
#     """Search wiki pages by game and query.
#     
#     Args:
#         game_key: Game identifier (eu4, hoi4, etc.)
#         query: Search query string
#         limit: Maximum results to return
#     
#     Returns:
#         List of matching pages with title, url, image_url
#     
#     Raises:
#         ValueError: If query validation fails
#         DatabaseError: If database query fails
#     """
```

#### 17. FIX SECURITY ISSUES
```python
# Path Traversal Prevention:
#   - Validate all game_key inputs
#   - Sanitize all filenames
#   - Never use untrusted strings in os.path.join directly
# 
# Input Validation:
#   - Validate query length and characters
#   - Validate game_key exists in config
#   - Validate user IDs are numeric strings
```

#### 18. CREATE BASIC TESTS
```python
# tests/unit/test_validators.py:
#   - Test QueryValidator.validate() with valid/invalid inputs
#   - Test GameKeyValidator.validate() with valid/invalid inputs
#   - Test FilenameValidator.sanitize() with dangerous filenames
# 
# tests/unit/test_database.py:
#   - Test DatabaseManager.get_db_path() validation
#   - Test search with empty results
#   - Test error handling
# 
# tests/unit/test_cache.py:
#   - Test cache hit/miss
#   - Test TTL expiration
#   - Test invalidation
# 
# tests/integration/test_bot_commands.py:
#   - Mock Discord context
#   - Test help command output
#   - Test search command with various queries
```

### CODE QUALITY REQUIREMENTS

1. **All code must pass:**
   - black (code formatting)
   - pylint (linting)
   - mypy (type checking)

2. **Docstrings required:**
   - Module docstrings
   - Class docstrings
   - Function/method docstrings with Args, Returns, Raises

3. **Logging instead of print:**
   - Replace all print() statements
   - Use structured logging with context

4. **Error messages:**
   - User-facing messages are friendly and clear
   - Log messages include technical details
   - No stack traces shown to users

5. **Comments:**
   - Code comments in English only
   - User-facing text (embeds, messages) can be Ukrainian
   - Comments explain WHY, not WHAT (code shows what)

### MIGRATION FROM OLD CODE

1. Keep all original functionality
2. Port all game styles (eu4, hoi4, stl, imp, vic3, ck3)
3. Keep search logic identical
4. Keep embed styling identical
5. Keep Discord reactions intact
6. Keep PDX.tools upload feature
7. Keep logging channel integration

### TESTING GUIDELINES

```python
# Use pytest with async support
# Test fixtures for mocking:
#   - mock_db
#   - mock_cache
#   - mock_discord_context
#   - mock_settings

# Run tests:
# pytest tests/ -v --cov=src --cov-report=html

# Coverage target: 70%+ of critical code
```

### FINAL DELIVERABLES

1. ✅ Fully refactored codebase with modular structure
2. ✅ All error handling implemented
3. ✅ All security issues fixed
4. ✅ Complete type hints throughout
5. ✅ Comprehensive logging
6. ✅ Configuration management system
7. ✅ Input validation and sanitization
8. ✅ Unit tests for critical functions
9. ✅ .env.example file
10. ✅ Updated requirements.txt
11. ✅ All original features preserved
12. ✅ Code follows Python best practices
13. ✅ Ready for production deployment

### DO NOT

- ❌ Break any existing functionality
- ❌ Change the bot's behavior or output
- ❌ Remove any features
- ❌ Use external APIs that aren't already in dependencies
- ❌ Create breaking changes to command syntax
- ❌ Ignore security issues
- ❌ Skip error handling

### DO

- ✅ Maintain backward compatibility
- ✅ Improve code quality and maintainability
- ✅ Add comprehensive error handling
- ✅ Add logging throughout
- ✅ Fix all security issues
- ✅ Add type hints
- ✅ Organize code into modules
- ✅ Keep the same output and behavior

---

## SUMMARY: Project Assessment

### Current State
- **Type:** Discord Bot for Paradox Game Wiki Navigation
- **Language:** Python 3.11+
- **Size:** ~310 lines in single file
- **Status:** Functional but needs refactoring

### Functionality (What It Does)
1. **Wiki Search** - Users can search 6 Paradox game wikis:
   - Europa Universalis 4 (`-eu4`)
   - Hearts of Iron 4 (`-hoi4`)
   - Stellaris (`-stl`)
   - Imperator (`-imp`)
   - Victoria 3 (`-vic3`)
   - Crusader Kings 3 (`-ck3`)

2. **Search Features:**
   - Exact match search first
   - Partial/fuzzy match fallback
   - Returns up to 7 results
   - Shows up to 5 clickable buttons
   - Rich Discord embeds with game-specific colors and logos

3. **File Uploads** - PDX.tools integration:
   - Users can upload save files
   - Bot processes and provides upload URL
   - Stores metadata in SQLite database

4. **Logging** - Search requests logged to Discord channel:
   - User information
   - Query details
   - Results found or not
   - Image presence

5. **Help Command** - Shows all available commands

### Technologies Used
- **discord.py** - Discord bot framework
- **SQLite3** - Local database for game data + uploads
- **Flask** - Health check endpoint (keep-alive)
- **python-dotenv** - Environment configuration

### Known Issues (Fixed by This Prompt)
1. ❌ **No error handling** - Operations fail silently
2. ❌ **Monolithic code** - Hard to maintain/test
3. ❌ **No logging** - Uses print() statements
4. ❌ **Hardcoded config** - Values scattered throughout
5. ❌ **Security vulnerabilities** - Path traversal possible
6. ❌ **No input validation** - Accepts dangerous input
7. ❌ **Incomplete requirements.txt** - Missing Flask dependency
8. ❌ **No type hints** - Difficult to maintain
9. ❌ **Blocking I/O** - File operations block async
10. ❌ **No testing** - No way to verify functionality

### Target Quality Level
**From:** Beginner (learning project)  
**To:** Senior (production-ready)

**Key Improvements:**
- Modular, maintainable architecture
- Production-grade error handling
- Comprehensive logging and monitoring
- Security hardening
- Type safety throughout
- Testable code design
- Professional configuration management
- Documentation and deployment-ready

### Deployment Ready
After this refactoring, the bot will be:
- ✅ Production-deployable
- ✅ Easily maintainable
- ✅ Scalable for new features
- ✅ Testable and debuggable
- ✅ Secure from common attacks
- ✅ Observable with logging
- ✅ Following Python best practices

### Expected Outcome
A well-structured, secure, maintainable Discord bot that searches Paradox game wikis and provides rich, interactive results to users while maintaining operational visibility through logging and monitoring.
