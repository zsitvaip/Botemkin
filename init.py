# Run this script to create empty config files.

configs = {
'config.py': """TOKEN = ''
ANNOUNCEMENTS_CHANNEL = ''
MOD_CHANNEL = ''
HOME_CHANNEL = ''
GENERAL_CHANNEL = ''
MATCHMAKING_CHANNEL = ''
WELCOME_TEXT = \"\"\"
\"\"\"
GUILD_ID = ''
SUPERUSER_ROLE = ''
RESTRICTED_ROLE = ''
ONBOARDING_ENABLED_DATE = ''""",

"cogs_config.py": """DETECT_LANGUAGE_API_KEY = ""
IGDB_CLIENT_ID = ""
IGDB_CLIENT_SECRET = ''""",

"debug_config.py" : """DEBUG_GUILD_ID = ""
DEBUG_ROLES = [
    # role name, igdb id, game name
    ["", "", ""],
    ["", "", ""]
]
DEBUG_DIR = ''"""}

for filename, content in configs.items():
    file = open(filename, "x")
    file.write(content)
    file.close()