from fastapi import FastAPI, Query, HTTPException, Request, Form
from dotenv import load_dotenv
import spotipy
from fastapi.responses import RedirectResponse, HTMLResponse
import os
from spotipy.oauth2 import SpotifyOAuth
from starlette.middleware.sessions import SessionMiddleware
from openai import OpenAI

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SECRET_KEY"))



SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
SPOTIFY_REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI")
SCOPE = "playlist-modify-public"

sp_oauth = SpotifyOAuth(
    client_id=SPOTIFY_CLIENT_ID,
    client_secret=SPOTIFY_CLIENT_SECRET,
    redirect_uri=SPOTIFY_REDIRECT_URI,
    scope=SCOPE
)


@app.get("/")
async def index():
   return {"message": "Hello World"}



def get_track_uri(item, sp):
   split = item.split("-")
   if len(split) != 2:
      return None
   song_name = split[0].strip()
   artist_name = split[1].strip()
   query = f"track:{song_name} artist:{artist_name}"

   results = sp.search(q=query, type='track', limit=1)
   tracks = results.get('tracks', {}).get('items', [])
   if tracks:
      return tracks[0]['uri']
   return None
   
@app.post("/gen_playlist")
def gen_playlist(request: Request, keywords: str = Form(...)):
   token_info = request.session.get("token_info")
   if not token_info or "access_token" not in token_info:
      return RedirectResponse(url="/login")
   
   buzzwords = [kw.strip() for kw in keywords.split(",") if kw.strip()]

   completion = client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {
            "role": "developer",
            "content": "You are a playlist generator api. Users will prompt you with a list of buzzwords. It is you rjob to create a spotify list of songs that mathches the vibes given in the list of buzzwords. There should be no other commentary in your response, only include the list of songs. Recommend atleast 40 songs. Shuffle it. Make a title for it and add it to the start of the list, Make the title witty as can be and in all lowercase. Make sure to not add any special characters to the title. The first line should be the title and the rest of the lines should be the songs. The songs should not be numbered and should be in the format of {song_name}-{artist_name}"
        }
        ,
        {
           "role":"user",
           "content": ",".join(buzzwords)
        }
    ]
   )
   response = completion.choices[0].message.content
   sp = spotipy.Spotify(auth=token_info["access_token"])
   current_user = sp.current_user()
   user_id = current_user["id"]

   response = response.split("\n")
   print(response)


   
   tracks = []
   for i in response[1:]:
      if i == "":
         continue
      track = get_track_uri(i, sp)
      # print(track)
      if (track):
         tracks.append(track)
   # print(tracks)
   if (len(tracks) == 0):
      tracks = ["spotify:track:1eajP3G86GZ0VEZgF8DeJS"]
      playlist_name = "No worky :("
   else:
      playlist_name = response[0]

   playlist = sp.user_playlist_create(user_id, playlist_name, public=True)
   playlist_id = playlist["id"]

   sp.playlist_add_items(playlist_id, tracks)


   


@app.get("/login")
def login():
    auth_url = sp_oauth.get_authorize_url()
    return RedirectResponse(auth_url)


@app.get("/callback")
def callback(request: Request, code: str = Query(None), state: str = Query(None)):
    if code:
        token = sp_oauth.get_access_token(code, check_cache=False)
        request.session["token_info"] = token
        return RedirectResponse(url="/enter")
    else:
        raise HTTPException(status_code=400, detail="Authorization failed.")
    

@app.get("/enter", response_class=HTMLResponse)
def keywords_page():
    html_content = """
    <html>
      <head>
        <title>Generate Playlist</title>
      </head>
      <body>
        <h1>Generate Playlist</h1>
        <form action="/gen_playlist" method="post">
          <label for="keywords">Enter keywords (comma separated):</label><br>
          <input type="text" id="keywords" name="keywords" style="width:300px"/><br><br>
          <button type="submit">Generate Playlist</button>
        </form>
      </body>
    </html>
    """
    return HTMLResponse(content=html_content)