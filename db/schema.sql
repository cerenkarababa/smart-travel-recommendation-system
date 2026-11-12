-- Preliminary schema only. Finalize after profiling the source CSV.
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_user_key TEXT UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS destinations (
    destination_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_destination_key TEXT UNIQUE,
    destination_name TEXT NOT NULL,
    country TEXT,
    region TEXT,
    climate TEXT,
    budget_level TEXT,
    best_season TEXT,
    description TEXT
);

CREATE TABLE IF NOT EXISTS travel_preferences (
    preference_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    season TEXT,
    budget_level TEXT,
    activity_level TEXT,
    safety_preference TEXT,
    popularity_preference TEXT,
    experience_preferences JSONB,
    scenery_preferences JSONB,
    region_preferences JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS destination_feedback (
    feedback_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    destination_id BIGINT NOT NULL REFERENCES destinations(destination_id),
    feedback_label SMALLINT NOT NULL CHECK (feedback_label IN (0, 1)),
    feedback_source TEXT NOT NULL DEFAULT 'dataset',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, destination_id, feedback_source)
);

CREATE TABLE IF NOT EXISTS recommendations (
    recommendation_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id BIGINT REFERENCES users(user_id) ON DELETE SET NULL,
    destination_id BIGINT NOT NULL REFERENCES destinations(destination_id),
    model_version TEXT NOT NULL,
    predicted_probability NUMERIC(6,5) NOT NULL
        CHECK (predicted_probability BETWEEN 0 AND 1),
    rank_position INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_feedback_user ON destination_feedback(user_id);
CREATE INDEX IF NOT EXISTS idx_feedback_destination ON destination_feedback(destination_id);
CREATE INDEX IF NOT EXISTS idx_recommendations_user_created
    ON recommendations(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_destinations_country ON destinations(country);
