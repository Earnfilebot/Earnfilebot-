package bot

import (
	"fmt"
	"log"
	"strings"

	tgbotapi "github.com/go-telegram-bot-api/telegram-bot-api/v5"
)

var CHANNELS = []string{
	"-1003712587847",
	"-1004395938795",
}

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

	// normalize command
	if idx := strings.Index(text, "@"); idx != -1 {
		text = text[:idx]
	}

	// 🔒 auto lock check (kalau user keluar channel)
	if !b.isJoined(msg.From.ID) && text != "/start" {
		b.sendForceJoin(msg.Chat.ID)
		return
	}

	switch text {

	case "/start":
		if b.isJoined(msg.From.ID) {
			b.sendDashboard(msg.Chat.ID, msg)
		} else {
			b.sendForceJoin(msg.Chat.ID)
		}

	case "/ping":
		b.reply(msg.Chat.ID, "🏓 Pong!")

	case "/help":
		b.reply(msg.Chat.ID, "Commands:\n/start\n/ping\n/help")

	default:
		b.reply(msg.Chat.ID, "❓ Command tidak dikenal")
	}
}

func (b *Bot) isJoined(userID int64) bool {
	for _, ch := range CHANNELS {
		member, err := b.api.GetChatMember(tgbotapi.ChatConfigWithUser{
			ChatID: ch,
			UserID: userID,
		})
		if err != nil {
			return false
		}

		if member.Status == "left" || member.Status == "kicked" {
			return false
		}
	}
	return true
}

func (b *Bot) sendForceJoin(chatID int64) {

	text := "🔒 BOT TERKUNCI\n\nKamu harus join semua channel dulu untuk akses bot."

	kb := tgbotapi.NewInlineKeyboardMarkup(
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonURL("📢 Join Channel 1", "https://t.me/channel1"),
		),
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonURL("📢 Join Channel 2", "https://t.me/channel2"),
		),
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("🔄 Check Access", "check"),
		),
	)

	msg := tgbotapi.NewMessage(chatID, text)
	msg.ReplyMarkup = kb

	b.api.Send(msg)
}

func (b *Bot) sendDashboard(chatID int64, msg *tgbotapi.Message) {

	text := "EARNFILEBOT\n\n" +
		"ID: " + fmt.Sprint(msg.From.ID) + "\n" +
		"Username: @" + msg.From.UserName + "\n" +
		"Balance: Rp 0 / $0\n\n" +
		"© earnfilebot"

	kb := tgbotapi.NewInlineKeyboardMarkup(
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("Upfile", "upfile"),
			tgbotapi.NewInlineKeyboardButtonData("Getfile", "getfile"),
		),
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("Account", "account"),
			tgbotapi.NewInlineKeyboardButtonData("Withdraw", "withdraw"),
		),
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("Help", "help"),
			tgbotapi.NewInlineKeyboardButtonData("About", "about"),
		),
	)

	m := tgbotapi.NewMessage(chatID, text)
	m.ReplyMarkup = kb

	b.api.Send(m)
}

func (b *Bot) reply(chatID int64, text string) {
	msg := tgbotapi.NewMessage(chatID, text)
	b.api.Send(msg)
}
