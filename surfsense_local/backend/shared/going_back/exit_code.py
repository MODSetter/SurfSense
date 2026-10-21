# Electron reads this exit as "a newer release upgraded the database" and offers
# to go back (electron/src/main/going-back/). Not 3: uvicorn exits 3 on any
# failed startup. Python uses 1, 2 and 120. Keep the two in step.
NEWER_DATABASE = 75
