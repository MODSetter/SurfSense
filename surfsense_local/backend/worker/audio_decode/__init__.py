"""A recording decoded to 16 kHz mono 16-bit PCM in a child process, worker.py's
--decode-audio mode, so a malformed file kills the child and never the ingest
consumer. pyminiaudio (MIT) reads WAV, MP3, FLAC and Ogg Vorbis."""
