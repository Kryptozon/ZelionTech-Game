-- ============================================================
-- Phase 18 migration — ZelionTech video-dependent, AI-resistant puzzles. Idempotent.
-- Adds official video URLs + hidden-clue placement, retires generic AI-solvable
-- puzzles, and seeds project-specific puzzles whose answers require watching the
-- official YouTube / TikTok hint videos.
-- ============================================================

-- ---- New puzzle fields (video-dependent design) ----
ALTER TABLE puzzles ADD COLUMN IF NOT EXISTS youtube_url             TEXT;
ALTER TABLE puzzles ADD COLUMN IF NOT EXISTS tiktok_url              TEXT;
ALTER TABLE puzzles ADD COLUMN IF NOT EXISTS hidden_clue_timestamp   TEXT;   -- e.g. "00:07"
ALTER TABLE puzzles ADD COLUMN IF NOT EXISTS hidden_clue_description TEXT;    -- admin-only placement note
ALTER TABLE puzzles ADD COLUMN IF NOT EXISTS clue_visible            BOOLEAN DEFAULT FALSE; -- reveal timestamp to users?
ALTER TABLE puzzle_scripts ADD COLUMN IF NOT EXISTS tiktok_script    TEXT;

-- Default official channel links where a specific video URL isn't set yet.
UPDATE puzzles SET youtube_url = 'https://www.youtube.com/@ZelionTech'      WHERE youtube_url IS NULL;
UPDATE puzzles SET tiktok_url  = 'https://www.tiktok.com/@zeliontech_zev'   WHERE tiktok_url  IS NULL;

-- ---- Retire generic AI-solvable puzzles (binary / Caesar / Morse / number sequences) ----
-- They stay in the bank for history but can never be released again.
UPDATE puzzles
   SET active = FALSE,
       status = 'closed'
 WHERE (
        category ILIKE '%binary%'   OR question ILIKE '%binary%'
     OR category ILIKE '%caesar%'   OR question ILIKE '%caesar%'
     OR category ILIKE '%morse%'    OR question ILIKE '%morse%'
     OR category ILIKE '%sequence%' OR question ILIKE '%sequence%'
     OR question ILIKE '%decode the%'
   )
   AND COALESCE(youtube_url,'') NOT LIKE '%watch?v=%';   -- don't touch real video puzzles

-- ---- Seed ZelionTech-specific, video-dependent puzzles (idempotent by slug) ----
-- All start as 'upcoming' + inactive; they NEVER auto-release. Admin releases manually.
-- Answers are placeholders the admin finalises per the actual video they publish.
INSERT INTO puzzles
  (slug, title, question, answer, accepted_variations, difficulty, reward, penalty,
   category, source_topic, source, status, active,
   youtube_instruction, telegram_instruction, explanation,
   hint1, hint2, hint3,
   youtube_url, tiktok_url, hidden_clue_timestamp, hidden_clue_description, clue_visible)
VALUES
  ('zt-timestamp-flash',
   'Flash Frame: Verified Energy',
   'A single word flashes for less than a second in today''s official TikTok hint. Watch carefully and enter that word.',
   'VERIFIED', 'verified,verified energy',
   'medium', 120, 10,
   'Video Timestamp', 'ZEV / Verified Energy', 'ZelionTech TikTok',
   'upcoming', FALSE,
   'Watch today''s TikTok hint frame-by-frame around the early seconds.',
   'A new hint video is live on YouTube and TikTok.',
   'The answer is the word that flashes in the official TikTok hint video — it is the first layer of the Zelion proof stack.',
   'It is hidden in the official TikTok video, not in this app.',
   'Pause the video around the 7-second mark.',
   'It is the first word in "Verified Energy".',
   'https://www.youtube.com/@ZelionTech', 'https://www.tiktok.com/@zeliontech_zev',
   '00:07', 'Single white-on-black frame flashes the word VERIFIED at ~0.4s.', FALSE),

  ('zt-reactor-symbol',
   'The Symbol Behind the ZEV',
   'In today''s official YouTube Short, a reactor symbol appears behind the ZEV device. Name that symbol.',
   'ATOM', 'atom,atom symbol,nucleus',
   'medium', 120, 10,
   'Visual Symbol', 'ZEV Device', 'ZelionTech YouTube',
   'upcoming', FALSE,
   'Look at the background of today''s YouTube Short when the ZEV device is shown.',
   'A new hint video is live on YouTube and TikTok.',
   'The glowing emblem behind the ZEV device is the Zelion reactor mark.',
   'It is visible only in the official YouTube Short.',
   'Look behind the device, not on it.',
   'It is the classic energy-core emblem.',
   'https://www.youtube.com/@ZelionTech', 'https://www.tiktok.com/@zeliontech_zev',
   '00:04', 'Atom/reactor emblem fades in behind the ZEV device between 0:03-0:06.', FALSE),

  ('zt-missing-layer',
   'The Missing Layer',
   'Today''s video shows the Zelion proof stack: "Verified Energy -> ? -> Digital Proof". Which Zelion layer is missing?',
   'ORACLE', 'oracle,zelion oracle,zyl oracle',
   'hard', 160, 10,
   'Project Terminology', 'Zelion Stack', 'ZelionTech YouTube + Website',
   'upcoming', FALSE,
   'The full stack is named in today''s YouTube hint and on the ZelionTech website.',
   'A new hint video is live on YouTube and TikTok.',
   'The Zelion flow is Verified Energy -> Oracle -> Digital Proof.',
   'It sits between raw energy and the final proof.',
   'It is named on the ZelionTech website and spoken in the video.',
   'It begins with O.',
   'https://www.youtube.com/@ZelionTech', 'https://www.tiktok.com/@zeliontech_zev',
   '00:12', 'Narrator names the middle layer "Oracle" at ~0:12 while the diagram is on screen.', FALSE),

  ('zt-multisource-combo',
   'Two-Source Cipher',
   'Combine the first hidden word shown in today''s YouTube hint with the symbol shown in today''s TikTok hint, then enter the single Zelion term they form.',
   'ZEVBRIDGE', 'zev bridge,zevbridge,bridge',
   'legendary', 220, 10,
   'Multi-Source', 'ZEV + Bridge', 'ZelionTech YouTube + TikTok',
   'upcoming', FALSE,
   'You need BOTH videos: the YouTube word and the TikTok symbol.',
   'A new hint video is live on YouTube and TikTok.',
   'YouTube reveals "ZEV"; TikTok reveals the Bridge mark — together: ZEV Bridge.',
   'One clue is on YouTube, the other on TikTok.',
   'The YouTube word is a 3-letter Zelion product.',
   'The TikTok symbol represents cross-chain transfer.',
   'https://www.youtube.com/@ZelionTech', 'https://www.tiktok.com/@zeliontech_zev',
   'YT 00:09 / TT 00:05', 'YouTube flashes "ZEV" at 0:09; TikTok shows the Bridge glyph at 0:05.', FALSE),

  ('zt-daily-code',
   'Daily Reactor Code',
   'The answer is the hidden code the admin places in today''s official YouTube/TikTok hint video. Watch and enter the exact code.',
   'ZLN-0000', 'zln0000,zln-0000',
   'easy', 100, 10,
   'Admin Daily Code', 'Daily Drop', 'ZelionTech YouTube + TikTok',
   'upcoming', FALSE,
   'The code appears on screen in today''s official hint video.',
   'A new hint video is live on YouTube and TikTok.',
   'The admin hides a ZLN-#### code in the video; that exact code is the answer.',
   'It always starts with "ZLN-".',
   'It appears as on-screen text in the official video.',
   'Enter it exactly, including the dash.',
   'https://www.youtube.com/@ZelionTech', 'https://www.tiktok.com/@zeliontech_zev',
   '00:15', 'Admin overlays the daily ZLN-#### code near the end of the video.', FALSE)
ON CONFLICT (slug) DO UPDATE SET
  title                  = EXCLUDED.title,
  question               = EXCLUDED.question,
  category               = EXCLUDED.category,
  source_topic           = EXCLUDED.source_topic,
  youtube_instruction    = EXCLUDED.youtube_instruction,
  telegram_instruction   = EXCLUDED.telegram_instruction,
  youtube_url            = EXCLUDED.youtube_url,
  tiktok_url             = EXCLUDED.tiktok_url,
  hidden_clue_timestamp  = EXCLUDED.hidden_clue_timestamp,
  hidden_clue_description= EXCLUDED.hidden_clue_description;

-- Generate matching admin scripts (YouTube + TikTok) for the seeded puzzles.
INSERT INTO puzzle_scripts (puzzle_id, youtube_title, youtube_script, tiktok_script, clue_timestamp, visual_clue, cta, telegram_post)
SELECT p.id,
       '⚡ Zelion Intelligence — ' || p.title,
       'INTRO: Welcome back, Operators. Today''s Reactor Intelligence puzzle is "' || p.title || '". ' ||
       'BODY: ' || p.question || ' Watch closely — the clue is hidden at ' || COALESCE(p.hidden_clue_timestamp,'a key moment') ||
       '. PLACEMENT: ' || COALESCE(p.hidden_clue_description,'(set placement in dashboard)') ||
       ' OUTRO: Submit your answer in the Zelion Reactor app. Only sharp eyes win.',
       'TikTok hook: "Blink and you''ll miss the Zelion code 👀" Show the clue at ' || COALESCE(p.hidden_clue_timestamp,'the drop') ||
       '. ' || COALESCE(p.hidden_clue_description,'') || ' End with: Answer in the Zelion Reactor app.',
       p.hidden_clue_timestamp,
       p.hidden_clue_description,
       'Submit in the Zelion Reactor Mini App',
       '⚡ New hint video is live on YouTube & TikTok. Watch, decode, and submit "' || p.title || '" in the app.'
FROM puzzles p
WHERE p.slug IN ('zt-timestamp-flash','zt-reactor-symbol','zt-missing-layer','zt-multisource-combo','zt-daily-code')
ON CONFLICT (puzzle_id) DO UPDATE SET
  youtube_script = EXCLUDED.youtube_script,
  tiktok_script  = EXCLUDED.tiktok_script,
  clue_timestamp = EXCLUDED.clue_timestamp,
  visual_clue    = EXCLUDED.visual_clue;

-- Walkthrough (admin-only) for each seeded puzzle.
UPDATE puzzles SET walkthrough =
  'Official solution: ' || explanation || ' The clue is placed at ' || COALESCE(hidden_clue_timestamp,'(set timestamp)') ||
  ' — ' || COALESCE(hidden_clue_description,'(set placement)') || '. Accepted answers: ' ||
  answer || COALESCE(', ' || accepted_variations,'') || '.'
WHERE slug IN ('zt-timestamp-flash','zt-reactor-symbol','zt-missing-layer','zt-multisource-combo','zt-daily-code');
