package bot

import (
	"log"
	"strings"

	tgbotapi "github.com/go-telegram-bot-api/telegram-bot-api/v5"
)

type Bot struct {
	api *tgbotapi.BotAPI
}

func NewBot(token string) (*Bot, error) {
	api, err := tgbotapi.NewBotAPI(token)
	if err != nil {
		return nil, err
	}

	api.Debug = false
	log.Println("Authorized:", api.Self.UserName)

	return &Bot{api: api}, nil
}

func (b *Bot) Start() {
	u := tgbotapi.NewUpdate(0)
	u.Timeout = 60

	updates := b.api.GetUpdatesChan(u)

	for update := range updates {
		if update.Message == nil {
			continue
		}

		b.handleMessage(update.Message)
	}
}

func (b *Bot) handleMessage(msg *tgbotapi.Message) {
	text := msg.Text

	// normalize command (hapus @botusername)
	if idx := strings.Index(text, "@"); idx != -1 {
		text = text[:idx]
	}

	switch text {

	case "/start":
		b.reply(msg.Chat.ID, "👋 Halo! Bot kamu sudah aktif.")

	case "/ping":
		b.reply(msg.Chat.ID, "🏓 Pong!")

	case "/help":
		b.reply(msg.Chat.ID, "Commands:\n/start\n/ping\n/help")

	default:
		b.reply(msg.Chat.ID, "❓ Command tidak dikenal")
	}
}

func (b *Bot) reply(chatID int64, text string) {
	msg := tgbotapi.NewMessage(chatID, text)
	b.api.Send(msg)
}
