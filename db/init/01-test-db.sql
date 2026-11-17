-- Runs once when the Postgres volume is first created.
-- A separate database for the backend test suite, so tests never touch dev data.
CREATE DATABASE immersion_test OWNER immersion;
