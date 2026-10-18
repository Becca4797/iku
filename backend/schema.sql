-- Which datasets we hold and when each was last refreshed
create table if not exists features (
  feature     text primary key,        -- 'crime', 'lighting', 'places'
  source      text not null,
  fetch_date  timestamptz,
  row_count   integer
);

-- Lets a loader resume where it stopped: one row per area tile fetched
create table if not exists fetch_tiles (
  feature     text not null,
  tile        text not null,           -- e.g. '51.30_-0.50'
  period      text not null default '', -- crime month like '2026-08', else ''
  fetched_at  timestamptz not null default now(),
  row_count   integer,
  primary key (feature, tile, period)
);

-- Police street crimes
create table if not exists crimes (
  id        bigint primary key,        -- police crime id, prevents duplicates
  category  text not null,
  month     text not null,             -- 'YYYY-MM'
  lat       double precision not null,
  lon       double precision not null
);
create index if not exists crimes_month_idx on crimes (month);

-- OpenStreetMap street lamps
create table if not exists lamps (
  osm_id  bigint primary key,
  lat     double precision not null,
  lon     double precision not null
);

-- OpenStreetMap streets with a lit=yes/no tag
create table if not exists lit_streets (
  osm_id  bigint primary key,
  lit     text not null,
  points  jsonb not null               -- [[lat, lon], ...]
);

-- Shops, police stations, hospitals and similar
create table if not exists places (
  place_id        text primary key,    -- e.g. 'osm:node:12345'
  name            text,
  types           text[] not null default '{}',
  lat             double precision not null,
  lon             double precision not null,
  business_status text not null default 'OPERATIONAL',
  opening_hours   jsonb,
  source          text not null,
  fetched_at      timestamptz not null default now()
);

insert into features (feature, source) values
  ('crime',    'data.police.uk'),
  ('lighting', 'OpenStreetMap'),
  ('places',   'OpenStreetMap')
on conflict (feature) do nothing;