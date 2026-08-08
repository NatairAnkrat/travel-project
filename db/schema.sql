CREATE TABLE "users" (
  "id" uuid PRIMARY KEY,
  "login" varchar(50) UNIQUE NOT NULL,
  "password_hash" varchar(255) NOT NULL,
  "email" varchar(255) UNIQUE NOT NULL,
  "phone" varchar(20) UNIQUE,
  "is_active" boolean NOT NULL DEFAULT true,
  "email_verified" boolean NOT NULL DEFAULT false,
  "created_at" timestamptz NOT NULL,
  "updated_at" timestamptz NOT NULL,
  "last_login" timestamptz
);

CREATE TABLE "user_profile" (
  "id" uuid PRIMARY KEY,
  "user_id" uuid UNIQUE NOT NULL,
  "first_name" varchar(100) NOT NULL,
  "last_name" varchar(100) NOT NULL,
  "middle_name" varchar(100),
  "birth_date" date,
  "gender" varchar(100),
  "avatar_url" text,
  "language_id" uuid NOT NULL,
  "timezone" varchar(100) NOT NULL,
  "created_at" timestamptz NOT NULL,
  "updated_at" timestamptz NOT NULL
);

CREATE TABLE "user_settings" (
  "id" uuid PRIMARY KEY,
  "user_id" uuid UNIQUE NOT NULL,
  "currency_id" uuid NOT NULL,
  "language_id" uuid NOT NULL,
  "theme" varchar(20) DEFAULT 'light',
  "distance_unit" varchar(20) DEFAULT 'km',
  "email_notifications" boolean DEFAULT true,
  "push_notifications" boolean DEFAULT true,
  "created_at" timestamptz NOT NULL,
  "updated_at" timestamptz NOT NULL
);

CREATE TABLE "user_sessions" (
  "id" uuid PRIMARY KEY,
  "user_id" uuid NOT NULL,
  "access_token" text NOT NULL,
  "device" varchar(255),
  "ip_address" inet,
  "expires_at" timestamptz NOT NULL,
  "created_at" timestamptz NOT NULL DEFAULT (now())
);

CREATE TABLE "refresh_tokens" (
  "id" uuid PRIMARY KEY,
  "user_id" uuid NOT NULL,
  "session_id" uuid NOT NULL,
  "token" text NOT NULL,
  "expires_at" timestamptz NOT NULL,
  "revoked" boolean NOT NULL DEFAULT false,
  "created_at" timestamptz NOT NULL DEFAULT (now())
);

CREATE TABLE "travel_groups" (
  "id" uuid PRIMARY KEY,
  "name" varchar(150) NOT NULL,
  "description" text,
  "status" varchar(30) NOT NULL,
  "created_at" timestamptz NOT NULL DEFAULT (now()),
  "updated_at" timestamptz NOT NULL DEFAULT (now())
);

CREATE TABLE "group_members" (
  "id" uuid PRIMARY KEY,
  "group_id" uuid NOT NULL,
  "user_id" uuid NOT NULL,
  "role_id" uuid NOT NULL,
  "joined_at" timestamptz NOT NULL,
  "status" varchar(30) NOT NULL
);

CREATE TABLE "invitations" (
  "id" uuid PRIMARY KEY,
  "group_id" uuid NOT NULL,
  "email" varchar(255) NOT NULL,
  "token" uuid UNIQUE NOT NULL,
  "status" varchar(30) NOT NULL,
  "created_by" uuid NOT NULL,
  "expires_at" timestamptz NOT NULL,
  "created_at" timestamptz NOT NULL
);

CREATE TABLE "notifications" (
  "id" uuid PRIMARY KEY,
  "type" varchar(50) NOT NULL,
  "title" varchar(255) NOT NULL,
  "message" text NOT NULL,
  "created_by" uuid,
  "created_at" timestamptz NOT NULL DEFAULT (now())
);

CREATE TABLE "user_notifications" (
  "id" uuid PRIMARY KEY,
  "notification_id" uuid NOT NULL,
  "user_id" uuid NOT NULL,
  "is_read" boolean NOT NULL DEFAULT false,
  "read_at" timestamptz,
  "created_at" timestamptz NOT NULL DEFAULT (now())
);

CREATE TABLE "favorites" (
  "id" uuid PRIMARY KEY,
  "user_id" uuid NOT NULL,
  "entity_type" varchar(50) NOT NULL,
  "entity_id" uuid NOT NULL,
  "created_at" timestamptz NOT NULL
);

CREATE TABLE "files" (
  "id" uuid PRIMARY KEY,
  "uploaded_by" uuid NOT NULL,
  "travel_version_id" uuid,
  "file_name" varchar(255) NOT NULL,
  "file_type" varchar(100) NOT NULL,
  "file_size" bigint NOT NULL,
  "storage_url" text NOT NULL,
  "created_at" timestamptz NOT NULL
);

CREATE TABLE "travels" (
  "id" uuid PRIMARY KEY,
  "group_id" uuid NOT NULL,
  "title" varchar(255) NOT NULL,
  "description" text,
  "destination_city_id" uuid NOT NULL,
  "start_date" date NOT NULL,
  "end_date" date NOT NULL,
  "status" varchar(30) NOT NULL,
  "created_by" uuid NOT NULL,
  "created_at" timestamptz DEFAULT (now()),
  "updated_at" timestamptz DEFAULT (now())
);

CREATE TABLE "travel_versions" (
  "id" uuid PRIMARY KEY,
  "travel_id" uuid NOT NULL,
  "version_number" integer NOT NULL,
  "description" text,
  "created_by" uuid NOT NULL,
  "is_current" boolean DEFAULT true,
  "created_at" timestamptz DEFAULT (now())
);

CREATE TABLE "user_travel_preferences" (
  "id" uuid PRIMARY KEY,
  "travel_version_id" uuid NOT NULL,
  "user_id" uuid NOT NULL,
  "departure_city_id" uuid NOT NULL,
  "departure_airport_id" uuid,
  "budget_limit" numeric(12,2),
  "currency_id" uuid NOT NULL,
  "preferred_transport" varchar(50),
  "preferred_food" varchar(100),
  "preferred_hotel_class" smallint,
  "seat_preference" varchar(30),
  "notes" text,
  "created_at" timestamptz NOT NULL DEFAULT (now()),
  "updated_at" timestamptz NOT NULL DEFAULT (now())
);

CREATE TABLE "search_requests" (
  "id" uuid PRIMARY KEY,
  "travel_version_id" uuid NOT NULL,
  "requested_by" uuid NOT NULL,
  "request_type" varchar(50) NOT NULL,
  "status" varchar(30) NOT NULL,
  "rquid" uuid UNIQUE NOT NULL,
  "started_at" timestamptz NOT NULL,
  "finished_at" timestamptz
);

CREATE TABLE "travel_events" (
  "id" uuid PRIMARY KEY,
  "travel_version_id" uuid NOT NULL,
  "user_id" uuid,
  "event_type" varchar(50) NOT NULL,
  "description" text,
  "created_at" timestamptz NOT NULL
);

CREATE TABLE "ai_jobs" (
  "id" uuid PRIMARY KEY,
  "travel_version_id" uuid NOT NULL,
  "search_request_id" uuid NOT NULL,
  "model_id" uuid NOT NULL,
  "prompt" text NOT NULL,
  "temperature" numeric(3,2) NOT NULL,
  "status" varchar(30) NOT NULL,
  "rquid" uuid NOT NULL,
  "started_at" timestamptz NOT NULL,
  "finished_at" timestamptz
);

CREATE TABLE "ai_results" (
  "id" uuid PRIMARY KEY,
  "job_id" uuid NOT NULL,
  "version" int NOT NULL,
  "score" numeric(5,2),
  "summary" text,
  "raw_response" json,
  "created_at" timestamptz NOT NULL DEFAULT (now())
);

CREATE TABLE "itineraries" (
  "id" uuid PRIMARY KEY,
  "travel_version_id" uuid NOT NULL,
  "ai_result_id" uuid NOT NULL,
  "title" varchar(255) NOT NULL,
  "description" text,
  "rating" numeric(5,2),
  "selected" boolean NOT NULL DEFAULT false,
  "created_at" timestamptz NOT NULL DEFAULT (now())
);

CREATE TABLE "itinerary_days" (
  "id" uuid PRIMARY KEY,
  "itinerary_id" uuid NOT NULL,
  "day_number" int NOT NULL,
  "date" date NOT NULL,
  "notes" text
);

CREATE TABLE "itinerary_items" (
  "id" uuid PRIMARY KEY,
  "day_id" uuid NOT NULL,
  "type" varchar(50) NOT NULL,
  "title" varchar(255) NOT NULL,
  "description" text,
  "start_time" timestamptz,
  "end_time" timestamptz,
  "latitude" numeric(10,7),
  "longitude" numeric(10,7),
  "external_reference" varchar(255)
);

CREATE TABLE "budget" (
  "id" uuid PRIMARY KEY,
  "travel_version_id" uuid UNIQUE NOT NULL,
  "tickets_cost" numeric(12,2) DEFAULT 0,
  "housing_cost" numeric(12,2) DEFAULT 0,
  "food_cost" numeric(12,2) DEFAULT 0,
  "transport_cost" numeric(12,2) DEFAULT 0,
  "activities_cost" numeric(12,2) DEFAULT 0,
  "other_cost" numeric(12,2) DEFAULT 0,
  "total_cost" numeric(12,2) DEFAULT 0,
  "currency_id" uuid NOT NULL
);

CREATE TABLE "votes" (
  "id" uuid PRIMARY KEY,
  "itinerary_id" uuid NOT NULL,
  "user_id" uuid NOT NULL,
  "vote" smallint NOT NULL,
  "comment" text,
  "created_at" timestamptz NOT NULL DEFAULT (now())
);

CREATE TABLE "providers" (
  "id" uuid PRIMARY KEY,
  "name" varchar(100) UNIQUE NOT NULL,
  "type" varchar(50) NOT NULL,
  "base_url" text NOT NULL,
  "api_version" varchar(30),
  "status" varchar(30) NOT NULL,
  "created_at" timestamptz NOT NULL DEFAULT (now())
);

CREATE TABLE "api_keys" (
  "id" uuid PRIMARY KEY,
  "provider_id" uuid NOT NULL,
  "api_key" text NOT NULL,
  "secret_key" text,
  "expires_at" timestamptz,
  "is_active" boolean NOT NULL DEFAULT true,
  "created_at" timestamptz NOT NULL DEFAULT (now())
);

CREATE TABLE "places" (
  "id" uuid PRIMARY KEY,
  "city_id" uuid NOT NULL,
  "country_id" uuid NOT NULL,
  "name" varchar(255) NOT NULL,
  "address" text,
  "postal_code" varchar(30),
  "latitude" numeric(10,7) NOT NULL,
  "longitude" numeric(10,7) NOT NULL,
  "google_place_id" varchar(255),
  "osm_id" varchar(255),
  "created_at" timestamptz NOT NULL DEFAULT (now())
);

CREATE TABLE "ticket_prices" (
  "id" uuid PRIMARY KEY,
  "ticket_id" uuid NOT NULL,
  "provider_id" uuid NOT NULL,
  "price" numeric(12,2) NOT NULL,
  "currency_id" uuid NOT NULL,
  "captured_at" timestamptz NOT NULL DEFAULT (now())
);

CREATE TABLE "accommodation_prices" (
  "id" uuid PRIMARY KEY,
  "accommodation_id" uuid NOT NULL,
  "provider_id" uuid NOT NULL,
  "price" numeric(12,2) NOT NULL,
  "currency_id" uuid NOT NULL,
  "captured_at" timestamptz NOT NULL DEFAULT (now())
);

CREATE TABLE "restaurant_prices" (
  "id" uuid PRIMARY KEY,
  "restaurant_id" uuid NOT NULL,
  "provider_id" uuid NOT NULL,
  "average_check" numeric(12,2) NOT NULL,
  "currency_id" uuid NOT NULL,
  "captured_at" timestamptz NOT NULL DEFAULT (now())
);

CREATE TABLE "transport_prices" (
  "id" uuid PRIMARY KEY,
  "transport_option_id" uuid NOT NULL,
  "provider_id" uuid NOT NULL,
  "price" numeric(12,2) NOT NULL,
  "currency_id" uuid NOT NULL,
  "captured_at" timestamptz NOT NULL DEFAULT (now())
);

CREATE TABLE "tickets" (
  "id" uuid PRIMARY KEY,
  "travel_version_id" uuid NOT NULL,
  "provider_id" uuid NOT NULL,
  "external_id" varchar(255) NOT NULL,
  "departure_airport_id" uuid NOT NULL,
  "arrival_airport_id" uuid NOT NULL,
  "departure_time" timestamptz NOT NULL,
  "arrival_time" timestamptz NOT NULL,
  "ticket_type" varchar(50) NOT NULL,
  "booking_class" varchar(30),
  "baggage_info" text,
  "booking_url" text,
  "status" varchar(30) NOT NULL,
  "last_updated" timestamptz NOT NULL DEFAULT (now())
);

CREATE TABLE "accommodations" (
  "id" uuid PRIMARY KEY,
  "travel_version_id" uuid NOT NULL,
  "provider_id" uuid NOT NULL,
  "place_id" uuid NOT NULL,
  "external_id" varchar(255) NOT NULL,
  "stars" smallint,
  "rating" numeric(3,2),
  "check_in" date,
  "check_out" date,
  "booking_url" text,
  "last_updated" timestamptz NOT NULL DEFAULT (now())
);

CREATE TABLE "restaurants" (
  "id" uuid PRIMARY KEY,
  "travel_version_id" uuid NOT NULL,
  "provider_id" uuid NOT NULL,
  "place_id" uuid NOT NULL,
  "external_id" varchar(255) NOT NULL,
  "cuisine" varchar(100),
  "rating" numeric(3,2),
  "price_level" smallint,
  "website" text,
  "opening_hours" text,
  "last_updated" timestamptz NOT NULL DEFAULT (now())
);

CREATE TABLE "attractions" (
  "id" uuid PRIMARY KEY,
  "travel_version_id" uuid NOT NULL,
  "provider_id" uuid NOT NULL,
  "place_id" uuid NOT NULL,
  "external_id" varchar(255) NOT NULL,
  "description" text,
  "rating" numeric(3,2),
  "opening_hours" text,
  "website" text,
  "last_updated" timestamptz NOT NULL DEFAULT (now())
);

CREATE TABLE "transport_options" (
  "id" uuid PRIMARY KEY,
  "travel_version_id" uuid NOT NULL,
  "provider_id" uuid NOT NULL,
  "external_id" varchar(255) NOT NULL,
  "transport_type" varchar(50) NOT NULL,
  "departure_place_id" uuid NOT NULL,
  "arrival_place_id" uuid NOT NULL,
  "departure_time" timestamptz,
  "arrival_time" timestamptz,
  "duration_minutes" int,
  "booking_url" text,
  "last_updated" timestamptz NOT NULL DEFAULT (now())
);

CREATE TABLE "weather_forecast" (
  "id" uuid PRIMARY KEY,
  "travel_version_id" uuid NOT NULL,
  "provider_id" uuid NOT NULL,
  "city_id" uuid NOT NULL,
  "forecast_date" date NOT NULL,
  "temperature_day" numeric(5,2),
  "temperature_night" numeric(5,2),
  "humidity" smallint,
  "wind_speed" numeric(5,2),
  "weather_description" varchar(255),
  "last_updated" timestamptz NOT NULL DEFAULT (now())
);

CREATE TABLE "integration_log" (
  "id" uuid PRIMARY KEY,
  "rquid" uuid NOT NULL,
  "rsuid" uuid UNIQUE NOT NULL,
  "search_request_id" uuid,
  "travel_version_id" uuid,
  "user_id" uuid,
  "provider_id" uuid NOT NULL,
  "service_name" varchar(100) NOT NULL,
  "endpoint" text NOT NULL,
  "http_method" varchar(10) NOT NULL,
  "request_headers" json,
  "request_body" json,
  "response_headers" json,
  "response_body" json,
  "response_status" int,
  "duration_ms" int,
  "success" boolean NOT NULL,
  "error_message" text,
  "created_at" timestamptz NOT NULL DEFAULT (now())
);

CREATE TABLE "audit_log" (
  "id" uuid PRIMARY KEY,
  "rquid" uuid,
  "rsuid" uuid,
  "user_id" uuid,
  "entity_name" varchar(100) NOT NULL,
  "entity_id" uuid NOT NULL,
  "action" varchar(30) NOT NULL,
  "old_value" json,
  "new_value" json,
  "ip_address" varchar(45),
  "user_agent" text,
  "created_at" timestamptz NOT NULL DEFAULT (now())
);

CREATE TABLE "countries" (
  "id" uuid PRIMARY KEY,
  "name" varchar(150) NOT NULL,
  "iso2" varchar(2) UNIQUE NOT NULL,
  "iso3" varchar(3) UNIQUE NOT NULL
);

CREATE TABLE "cities" (
  "id" uuid PRIMARY KEY,
  "country_id" uuid NOT NULL,
  "name" varchar(150) NOT NULL,
  "latitude" numeric(10,7),
  "longitude" numeric(10,7),
  "timezone" varchar(100)
);

CREATE TABLE "airports" (
  "id" uuid PRIMARY KEY,
  "city_id" uuid NOT NULL,
  "iata_code" varchar(3) UNIQUE NOT NULL,
  "icao_code" varchar(4),
  "name" varchar(255) NOT NULL,
  "latitude" numeric(10,7),
  "longitude" numeric(10,7)
);

CREATE TABLE "currencies" (
  "id" uuid PRIMARY KEY,
  "code" varchar(3) UNIQUE NOT NULL,
  "name" varchar(100) NOT NULL,
  "symbol" varchar(10)
);

CREATE TABLE "languages" (
  "id" uuid PRIMARY KEY,
  "code" varchar(10) UNIQUE NOT NULL,
  "name" varchar(100) NOT NULL
);

CREATE TABLE "ai_models" (
  "id" uuid PRIMARY KEY,
  "provider_id" uuid NOT NULL,
  "model_name" varchar(100) NOT NULL,
  "version" varchar(30),
  "description" text,
  "is_active" boolean NOT NULL DEFAULT true,
  "created_at" timestamptz NOT NULL DEFAULT (now())
);

CREATE TABLE "group_roles" (
  "id" uuid PRIMARY KEY,
  "code" varchar(30) UNIQUE NOT NULL,
  "name" varchar(100) NOT NULL,
  "description" text,
  "created_at" timestamptz NOT NULL DEFAULT (now())
);

CREATE UNIQUE INDEX ON "group_members" ("group_id", "user_id");

CREATE UNIQUE INDEX ON "user_notifications" ("notification_id", "user_id");

CREATE UNIQUE INDEX ON "travel_versions" ("travel_id", "version_number");

CREATE UNIQUE INDEX ON "user_travel_preferences" ("travel_version_id", "user_id");

CREATE UNIQUE INDEX ON "itinerary_days" ("itinerary_id", "day_number");

CREATE UNIQUE INDEX ON "votes" ("itinerary_id", "user_id");

CREATE UNIQUE INDEX ON "tickets" ("provider_id", "external_id");

CREATE UNIQUE INDEX ON "accommodations" ("provider_id", "external_id");

CREATE UNIQUE INDEX ON "restaurants" ("provider_id", "external_id");

CREATE UNIQUE INDEX ON "attractions" ("provider_id", "external_id");

CREATE UNIQUE INDEX ON "transport_options" ("provider_id", "external_id");

ALTER TABLE "user_profile" ADD FOREIGN KEY ("user_id") REFERENCES "users" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "user_settings" ADD FOREIGN KEY ("user_id") REFERENCES "users" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "user_settings" ADD FOREIGN KEY ("currency_id") REFERENCES "currencies" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "user_settings" ADD FOREIGN KEY ("language_id") REFERENCES "languages" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "user_profile" ADD FOREIGN KEY ("language_id") REFERENCES "languages" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "user_sessions" ADD FOREIGN KEY ("user_id") REFERENCES "users" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "refresh_tokens" ADD FOREIGN KEY ("user_id") REFERENCES "users" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "refresh_tokens" ADD FOREIGN KEY ("session_id") REFERENCES "user_sessions" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "group_members" ADD FOREIGN KEY ("group_id") REFERENCES "travel_groups" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "group_members" ADD FOREIGN KEY ("user_id") REFERENCES "users" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "group_members" ADD FOREIGN KEY ("role_id") REFERENCES "group_roles" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "invitations" ADD FOREIGN KEY ("group_id") REFERENCES "travel_groups" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "invitations" ADD FOREIGN KEY ("created_by") REFERENCES "users" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "travels" ADD FOREIGN KEY ("group_id") REFERENCES "travel_groups" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "travels" ADD FOREIGN KEY ("destination_city_id") REFERENCES "cities" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "travels" ADD FOREIGN KEY ("created_by") REFERENCES "users" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "travel_versions" ADD FOREIGN KEY ("travel_id") REFERENCES "travels" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "travel_versions" ADD FOREIGN KEY ("created_by") REFERENCES "users" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "user_travel_preferences" ADD FOREIGN KEY ("travel_version_id") REFERENCES "travel_versions" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "user_travel_preferences" ADD FOREIGN KEY ("user_id") REFERENCES "users" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "user_travel_preferences" ADD FOREIGN KEY ("departure_city_id") REFERENCES "cities" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "user_travel_preferences" ADD FOREIGN KEY ("departure_airport_id") REFERENCES "airports" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "user_travel_preferences" ADD FOREIGN KEY ("currency_id") REFERENCES "currencies" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "travel_events" ADD FOREIGN KEY ("travel_version_id") REFERENCES "travel_versions" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "travel_events" ADD FOREIGN KEY ("user_id") REFERENCES "users" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "search_requests" ADD FOREIGN KEY ("travel_version_id") REFERENCES "travel_versions" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "search_requests" ADD FOREIGN KEY ("requested_by") REFERENCES "users" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "ai_jobs" ADD FOREIGN KEY ("travel_version_id") REFERENCES "travel_versions" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "ai_jobs" ADD FOREIGN KEY ("search_request_id") REFERENCES "search_requests" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "ai_jobs" ADD FOREIGN KEY ("model_id") REFERENCES "ai_models" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "ai_results" ADD FOREIGN KEY ("job_id") REFERENCES "ai_jobs" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "itineraries" ADD FOREIGN KEY ("travel_version_id") REFERENCES "travel_versions" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "itineraries" ADD FOREIGN KEY ("ai_result_id") REFERENCES "ai_results" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "itinerary_days" ADD FOREIGN KEY ("itinerary_id") REFERENCES "itineraries" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "itinerary_items" ADD FOREIGN KEY ("day_id") REFERENCES "itinerary_days" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "budget" ADD FOREIGN KEY ("travel_version_id") REFERENCES "travel_versions" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "budget" ADD FOREIGN KEY ("currency_id") REFERENCES "currencies" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "votes" ADD FOREIGN KEY ("itinerary_id") REFERENCES "itineraries" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "votes" ADD FOREIGN KEY ("user_id") REFERENCES "users" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "files" ADD FOREIGN KEY ("uploaded_by") REFERENCES "users" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "files" ADD FOREIGN KEY ("travel_version_id") REFERENCES "travel_versions" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "favorites" ADD FOREIGN KEY ("user_id") REFERENCES "users" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "notifications" ADD FOREIGN KEY ("created_by") REFERENCES "users" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "user_notifications" ADD FOREIGN KEY ("notification_id") REFERENCES "notifications" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "user_notifications" ADD FOREIGN KEY ("user_id") REFERENCES "users" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "api_keys" ADD FOREIGN KEY ("provider_id") REFERENCES "providers" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "ai_models" ADD FOREIGN KEY ("provider_id") REFERENCES "providers" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "places" ADD FOREIGN KEY ("city_id") REFERENCES "cities" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "places" ADD FOREIGN KEY ("country_id") REFERENCES "countries" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "tickets" ADD FOREIGN KEY ("travel_version_id") REFERENCES "travel_versions" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "tickets" ADD FOREIGN KEY ("provider_id") REFERENCES "providers" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "tickets" ADD FOREIGN KEY ("departure_airport_id") REFERENCES "airports" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "tickets" ADD FOREIGN KEY ("arrival_airport_id") REFERENCES "airports" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "ticket_prices" ADD FOREIGN KEY ("ticket_id") REFERENCES "tickets" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "ticket_prices" ADD FOREIGN KEY ("provider_id") REFERENCES "providers" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "ticket_prices" ADD FOREIGN KEY ("currency_id") REFERENCES "currencies" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "accommodations" ADD FOREIGN KEY ("travel_version_id") REFERENCES "travel_versions" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "accommodations" ADD FOREIGN KEY ("provider_id") REFERENCES "providers" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "accommodations" ADD FOREIGN KEY ("place_id") REFERENCES "places" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "accommodation_prices" ADD FOREIGN KEY ("accommodation_id") REFERENCES "accommodations" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "accommodation_prices" ADD FOREIGN KEY ("provider_id") REFERENCES "providers" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "accommodation_prices" ADD FOREIGN KEY ("currency_id") REFERENCES "currencies" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "restaurants" ADD FOREIGN KEY ("travel_version_id") REFERENCES "travel_versions" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "restaurants" ADD FOREIGN KEY ("provider_id") REFERENCES "providers" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "restaurants" ADD FOREIGN KEY ("place_id") REFERENCES "places" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "restaurant_prices" ADD FOREIGN KEY ("restaurant_id") REFERENCES "restaurants" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "restaurant_prices" ADD FOREIGN KEY ("provider_id") REFERENCES "providers" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "restaurant_prices" ADD FOREIGN KEY ("currency_id") REFERENCES "currencies" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "attractions" ADD FOREIGN KEY ("travel_version_id") REFERENCES "travel_versions" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "attractions" ADD FOREIGN KEY ("provider_id") REFERENCES "providers" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "attractions" ADD FOREIGN KEY ("place_id") REFERENCES "places" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "transport_options" ADD FOREIGN KEY ("travel_version_id") REFERENCES "travel_versions" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "transport_options" ADD FOREIGN KEY ("provider_id") REFERENCES "providers" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "transport_options" ADD FOREIGN KEY ("departure_place_id") REFERENCES "places" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "transport_options" ADD FOREIGN KEY ("arrival_place_id") REFERENCES "places" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "transport_prices" ADD FOREIGN KEY ("transport_option_id") REFERENCES "transport_options" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "transport_prices" ADD FOREIGN KEY ("provider_id") REFERENCES "providers" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "transport_prices" ADD FOREIGN KEY ("currency_id") REFERENCES "currencies" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "weather_forecast" ADD FOREIGN KEY ("travel_version_id") REFERENCES "travel_versions" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "weather_forecast" ADD FOREIGN KEY ("provider_id") REFERENCES "providers" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "weather_forecast" ADD FOREIGN KEY ("city_id") REFERENCES "cities" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "integration_log" ADD FOREIGN KEY ("search_request_id") REFERENCES "search_requests" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "integration_log" ADD FOREIGN KEY ("travel_version_id") REFERENCES "travel_versions" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "integration_log" ADD FOREIGN KEY ("user_id") REFERENCES "users" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "integration_log" ADD FOREIGN KEY ("provider_id") REFERENCES "providers" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "audit_log" ADD FOREIGN KEY ("user_id") REFERENCES "users" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "cities" ADD FOREIGN KEY ("country_id") REFERENCES "countries" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "airports" ADD FOREIGN KEY ("city_id") REFERENCES "cities" ("id") DEFERRABLE INITIALLY IMMEDIATE;
