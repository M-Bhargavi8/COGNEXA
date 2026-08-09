from templates.register import register
from auth.login import login
from core.leaderboard import show_leaderboard

while True:
    print("""
1. Register
2. Login
3. Leaderboard
4. Exit
    """)

    choice = input("Choose: ")

    if choice == "1":
        register()
    elif choice == "2":
        login()
    elif choice == "3":
        show_leaderboard()
    else:
        break