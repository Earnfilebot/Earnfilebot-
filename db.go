package db

import (
	"context"
	"log"
	"os"

	"github.com/jackc/pgx/v5/pgxpool"
)

var Pool *pgxpool.Pool

func Init() {
	url := os.Getenv("DATABASE_URL")
	if url == "" {
		log.Fatal("DATABASE_URL tidak ditemukan")
	}

	config, err := pgxpool.ParseConfig(url)
	if err != nil {
		log.Fatal(err)
	}

	config.ConnConfig.RuntimeParams["sslmode"] = "require"

	pool, err := pgxpool.NewWithConfig(context.Background(), config)
	if err != nil {
		log.Fatal(err)
	}

	Pool = pool

	log.Println("Neon DB connected")
}
