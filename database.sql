PRAGMA foreign_keys = ON;

BEGIN TRANSACTION;


-- ============================================================
-- USERS
-- ============================================================

CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,

    telegram_id     INTEGER NOT NULL UNIQUE,

    username        TEXT,

    first_name      TEXT,

    last_name       TEXT,

    created_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    is_active       INTEGER NOT NULL DEFAULT 1,

    CHECK (is_active IN (0, 1))
);


-- ============================================================
-- TOURNAMENTS
-- ============================================================

CREATE TABLE IF NOT EXISTS tournaments (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,

    name            TEXT NOT NULL,

    season          TEXT NOT NULL,

    total_rounds    INTEGER NOT NULL DEFAULT 8,

    status          TEXT NOT NULL DEFAULT 'upcoming',

    created_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CHECK (total_rounds > 0),

    CHECK (
        status IN (
            'upcoming',
            'active',
            'finished',
            'archived'
        )
    )
);


-- ============================================================
-- TELEGRAM GROUPS
-- ============================================================

CREATE TABLE IF NOT EXISTS telegram_groups (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,

    telegram_chat_id    INTEGER NOT NULL UNIQUE,

    title               TEXT NOT NULL,

    tournament_id       INTEGER NOT NULL,

    created_at          TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    is_active           INTEGER NOT NULL DEFAULT 1,

    FOREIGN KEY (tournament_id)
        REFERENCES tournaments(id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CHECK (is_active IN (0, 1))
);


-- ============================================================
-- PARTICIPANTS
-- ============================================================

CREATE TABLE IF NOT EXISTS participants (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,

    tournament_id   INTEGER NOT NULL,

    user_id         INTEGER NOT NULL,

    joined_at       TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    is_active       INTEGER NOT NULL DEFAULT 1,

    FOREIGN KEY (tournament_id)
        REFERENCES tournaments(id)
        ON UPDATE CASCADE
        ON DELETE CASCADE,

    FOREIGN KEY (user_id)
        REFERENCES users(id)
        ON UPDATE CASCADE
        ON DELETE CASCADE,

    UNIQUE (tournament_id, user_id),

    CHECK (is_active IN (0, 1))
);


-- ============================================================
-- ADMINS
-- ============================================================

CREATE TABLE IF NOT EXISTS admins (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,

    user_id         INTEGER NOT NULL UNIQUE,

    created_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id)
        REFERENCES users(id)
        ON UPDATE CASCADE
        ON DELETE CASCADE
);


-- ============================================================
-- ROUNDS
-- ============================================================

CREATE TABLE IF NOT EXISTS rounds (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,

    tournament_id   INTEGER NOT NULL,

    round_number    INTEGER NOT NULL,

    name            TEXT,

    status          TEXT NOT NULL DEFAULT 'upcoming',

    created_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (tournament_id)
        REFERENCES tournaments(id)
        ON UPDATE CASCADE
        ON DELETE CASCADE,

    UNIQUE (tournament_id, round_number),

    CHECK (round_number > 0),

    CHECK (
        status IN (
            'upcoming',
            'open',
            'closed',
            'finished'
        )
    )
);


-- ============================================================
-- MATCHES
-- ============================================================

CREATE TABLE IF NOT EXISTS matches (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,

    round_id        INTEGER NOT NULL,

    match_number    INTEGER NOT NULL,

    home_team       TEXT NOT NULL,

    away_team       TEXT NOT NULL,

    kickoff_at      TEXT NOT NULL,

    status          TEXT NOT NULL DEFAULT 'scheduled',

    created_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (round_id)
        REFERENCES rounds(id)
        ON UPDATE CASCADE
        ON DELETE CASCADE,

    UNIQUE (round_id, match_number),

    CHECK (match_number > 0),

    CHECK (length(trim(home_team)) > 0),

    CHECK (length(trim(away_team)) > 0),

    CHECK (home_team <> away_team),

    CHECK (
        status IN (
            'scheduled',
            'live',
            'finished',
            'postponed',
            'cancelled'
        )
    )
);


-- ============================================================
-- TEAM ASSETS
-- ============================================================

CREATE TABLE IF NOT EXISTS team_assets (

    id              INTEGER PRIMARY KEY AUTOINCREMENT,

    team_name       TEXT NOT NULL UNIQUE,

    display_name    TEXT,

    logo_url        TEXT,

    country_code    TEXT,

    flag_emoji      TEXT,

    updated_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT OR IGNORE INTO team_assets (
    team_name,
    display_name,
    country_code,
    flag_emoji
)
VALUES
    ('AEK Athens FC', 'АЕК Афины', 'GRE', '🇬🇷'),
    ('Arsenal', 'Арсенал', 'ENG', '🏴'),
    ('Aston Villa', 'Астон Вилла', 'ENG', '🏴'),
    ('Atletico Madrid', 'Атлетико Мадрид', 'ESP', '🇪🇸'),
    ('Barcelona', 'Барселона', 'ESP', '🇪🇸'),
    ('Bayern München', 'Бавария', 'DEU', '🇩🇪'),
    ('Bodo/Glimt', 'Буде-Глимт', 'NOR', '🇳🇴'),
    ('Borussia Dortmund', 'Боруссия Дортмунд', 'DEU', '🇩🇪'),
    ('Club Brugge KV', 'Брюгге', 'BEL', '🇧🇪'),
    ('Como', 'Комо', 'ITA', '🇮🇹'),
    ('Fenerbahçe', 'Фенербахче', 'TUR', '🇹🇷'),
    ('Feyenoord', 'Фейеноорд', 'NED', '🇳🇱'),
    ('Galatasaray', 'Галатасарай', 'TUR', '🇹🇷'),
    ('Inter', 'Интер', 'ITA', '🇮🇹'),
    ('Lask Linz', 'ЛАСК', 'AUT', '🇦🇹'),
    ('RB Leipzig', 'Лейпциг', 'DEU', '🇩🇪'),
    ('Lens', 'Ланс', 'FRA', '🇫🇷'),
    ('Lille', 'Лилль', 'FRA', '🇫🇷'),
    ('Liverpool', 'Ливерпуль', 'ENG', '🏴'),
    ('Manchester City', 'Манчестер Сити', 'ENG', '🏴'),
    ('Manchester United', 'Манчестер Юнайтед', 'ENG', '🏴'),
    ('Napoli', 'Наполи', 'ITA', '🇮🇹'),
    ('Paris Saint Germain', 'Пари Сен-Жермен', 'FRA', '🇫🇷'),
    ('FC Porto', 'Порту', 'POR', '🇵🇹'),
    ('PSV Eindhoven', 'ПСВ', 'NED', '🇳🇱'),
    ('Real Betis', 'Бетис', 'ESP', '🇪🇸'),
    ('Real Madrid', 'Реал Мадрид', 'ESP', '🇪🇸'),
    ('AS Roma', 'Рома', 'ITA', '🇮🇹'),
    ('Sabah FA', 'Сабах', 'AZE', '🇦🇿'),
    ('Shakhtar Donetsk', 'Шахтер', 'UKR', '🇺🇦'),
    ('Slavia Praha', 'Славия Прага', 'CZE', '🇨🇿'),
    ('Slovan Bratislava', 'Слован Братислава', 'SVK', '🇸🇰'),
    ('Sporting CP', 'Спортинг', 'POR', '🇵🇹'),
    ('VfB Stuttgart', 'Штутгарт', 'DEU', '🇩🇪'),
    ('Viking', 'Викинг', 'NOR', '🇳🇴'),
    ('Villarreal', 'Вильяреал', 'ESP', '🇪🇸');


-- ============================================================
-- MATCH RESULTS
-- ============================================================

CREATE TABLE IF NOT EXISTS match_results (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,

    match_id        INTEGER NOT NULL UNIQUE,

    home_score      INTEGER NOT NULL,

    away_score      INTEGER NOT NULL,

    status          TEXT NOT NULL DEFAULT 'confirmed',

    source          TEXT NOT NULL DEFAULT 'manual',

    updated_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (match_id)
        REFERENCES matches(id)
        ON UPDATE CASCADE
        ON DELETE CASCADE,

    CHECK (home_score >= 0),

    CHECK (away_score >= 0),

    CHECK (
        status IN (
            'pending',
            'confirmed',
            'corrected'
        )
    ),

    CHECK (
        source IN (
            'manual',
            'api'
        )
    )
);


-- ============================================================
-- PREDICTIONS
-- ============================================================

CREATE TABLE IF NOT EXISTS predictions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,

    participant_id  INTEGER NOT NULL,

    match_id        INTEGER NOT NULL,

    home_score      INTEGER NOT NULL,

    away_score      INTEGER NOT NULL,

    created_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    updated_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    locked_at       TEXT,

    FOREIGN KEY (participant_id)
        REFERENCES participants(id)
        ON UPDATE CASCADE
        ON DELETE CASCADE,

    FOREIGN KEY (match_id)
        REFERENCES matches(id)
        ON UPDATE CASCADE
        ON DELETE CASCADE,

    UNIQUE (participant_id, match_id),

    CHECK (home_score >= 0),

    CHECK (away_score >= 0)
);


-- ============================================================
-- PREDICTION SCORES
-- ============================================================

CREATE TABLE IF NOT EXISTS prediction_scores (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,

    prediction_id       INTEGER NOT NULL UNIQUE,

    points              INTEGER NOT NULL DEFAULT 0,

    exact_score         INTEGER NOT NULL DEFAULT 0,

    correct_difference  INTEGER NOT NULL DEFAULT 0,

    correct_outcome     INTEGER NOT NULL DEFAULT 0,

    calculated_at       TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (prediction_id)
        REFERENCES predictions(id)
        ON UPDATE CASCADE
        ON DELETE CASCADE,

    CHECK (points >= 0),

    CHECK (exact_score IN (0, 1)),

    CHECK (correct_difference IN (0, 1)),

    CHECK (correct_outcome IN (0, 1))
);


-- ============================================================
-- PREDICTION REMINDERS
-- ============================================================

CREATE TABLE IF NOT EXISTS prediction_reminders (

    id              INTEGER PRIMARY KEY AUTOINCREMENT,

    user_id         INTEGER NOT NULL,

    match_id        INTEGER NOT NULL,

    sent_at         TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id)
        REFERENCES users(id)
        ON DELETE CASCADE,

    FOREIGN KEY (match_id)
        REFERENCES matches(id)
        ON DELETE CASCADE,

    UNIQUE (user_id, match_id)
);


-- ============================================================
-- INDEXES
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_groups_tournament
    ON telegram_groups(tournament_id);

CREATE INDEX IF NOT EXISTS idx_participants_tournament
    ON participants(tournament_id);

CREATE INDEX IF NOT EXISTS idx_participants_user
    ON participants(user_id);

CREATE INDEX IF NOT EXISTS idx_rounds_tournament
    ON rounds(tournament_id);

CREATE INDEX IF NOT EXISTS idx_rounds_status
    ON rounds(status);

CREATE INDEX IF NOT EXISTS idx_matches_round
    ON matches(round_id);

CREATE INDEX IF NOT EXISTS idx_matches_kickoff
    ON matches(kickoff_at);

CREATE INDEX IF NOT EXISTS idx_matches_status
    ON matches(status);

CREATE INDEX IF NOT EXISTS idx_predictions_participant
    ON predictions(participant_id);

CREATE INDEX IF NOT EXISTS idx_predictions_match
    ON predictions(match_id);

CREATE INDEX IF NOT EXISTS idx_prediction_reminders_match
    ON prediction_reminders(match_id);


COMMIT;