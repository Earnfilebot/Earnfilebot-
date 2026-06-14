package bot

import (
	"fmt"
	"log"
	"strings"

	tgbotapi "github.com/go-telegram-bot-api/telegram-bot-api/v5"
)

var CHANNELS = []int64{
	-1003712587847,
	-1004395938795,
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

		if update.Message != nil {
			b.handleMessage(update.Message)
		}

		if update.CallbackQuery != nil {
			b.handleCallback(update.CallbackQuery)
		}
	}
}

func (b *Bot) handleMessage(msg *tgbotapi.Message) {

	text := strings.TrimSpace(msg.Text)

	if idx := strings.Index(text, "@"); idx != -1 {
		text = text[:idx]
	}

	switch text {

	case "/start":

		if b.isJoined(msg.From.ID) {
			b.sendDashboard(msg.Chat.ID, msg)
		} else {
			b.sendForceJoin(msg.Chat.ID)
		}

	case "/ping":

		if !b.isJoined(msg.From.ID) {
			b.sendForceJoin(msg.Chat.ID)
			return
		}

		b.reply(msg.Chat.ID, "🏓 Pong!")

	case "/help":

		if !b.isJoined(msg.From.ID) {
			b.sendForceJoin(msg.Chat.ID)
			return
		}

		b.reply(msg.Chat.ID, "Commands:\n/start\n/ping\n/help")

	default:

		if !b.isJoined(msg.From.ID) {
			b.sendForceJoin(msg.Chat.ID)
			return
		}

		b.reply(msg.Chat.ID, "❓ Command tidak dikenal")
	}
}
func (b *Bot) handleCallback(q *tgbotapi.CallbackQuery) {

	switch q.Data {

	case "check":

		if b.isJoined(q.From.ID) {

			// hapus pesan force join
			del := tgbotapi.NewDeleteMessage(
				q.Message.Chat.ID,
				q.Message.MessageID,
			)

			_, _ = b.api.Request(del)

			// tampilkan dashboard
			fakeMsg := &tgbotapi.Message{
				Chat: q.Message.Chat,
				From: q.From,
			}

			b.sendDashboard(
				q.Message.Chat.ID,
				fakeMsg,
			)

			_, _ = b.api.Request(
				tgbotapi.NewCallback(q.ID, "✅ Akses diberikan"),
			)

		} else {

			_, _ = b.api.Request(
				tgbotapi.NewCallback(q.ID, "❌ Kamu belum join semua channel"),
			)
		}
	}
}

func (b *Bot) isJoined(userID int64) bool {

	for _, ch := range CHANNELS {

		member, err := b.api.GetChatMember(
			tgbotapi.ChatConfigWithUser{
				ChatID: ch,
				UserID: userID,
			},
		)

		if err != nil {
			log.Println("Check member error:", ch, err)
			return false
		}

		switch member.Status {

		case "member", "administrator", "creator":
			continue

		case "left", "kicked":
			return false

		default:
			return false
		}
	}

	return true
}
func (b *Bot) sendForceJoin(chatID int64) {

	text := "🔒 BOT TERKUNCI\n\nKamu harus join kedua channel terlebih dahulu untuk menggunakan bot."

	kb := tgbotapi.NewInlineKeyboardMarkup(
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonURL(
				"📢 Channel 1",
				"https://t.me/+JL4ELKQCyckwMjFl",
			),
		),
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonURL(
				"📢 Channel 2",
				"https://t.me/+DTL9cOR34ipmM2U1",
			),
		),
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData(
				"✅ Check Access",
				"check",
			),
		),
	)

	msg := tgbotapi.NewMessage(chatID, text)
	msg.ReplyMarkup = kb

	b.api.Send(msg)
}

func (b *Bot) sendDashboard(chatID int64, msg *tgbotapi.Message) {

	username := msg.From.UserName
	if username == "" {
		username = "-"
	}

	text := "EARNFILEBOT\n\n" +
		"🆔ID: " + fmt.Sprint(msg.From.ID) + "\n" +
		"👤Username: " + username + "\n" +
		"💰Balance: Rp 0 / $0\n\n" +
		"<i>copyright by earnfilebot<i>"

	kb := tgbotapi.NewInlineKeyboardMarkup(
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("📤 Upfile", "upfile"),
			tgbotapi.NewInlineKeyboardButtonData("📥 Getfile", "getfile"),
		),
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("👤 Account", "account"),
			tgbotapi.NewInlineKeyboardButtonData("💸 Withdraw", "withdraw"),
		),
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("❓ Help", "help"),
			tgbotapi.NewInlineKeyboardButtonData("ℹ️ About", "about"),
		),
	)

	m := tgbotapi.NewMessage(chatID, text)
	m.ParseMode = "HTML"
	m.ReplyMarkup = kb

	_, _ = b.api.Send(m)
}

func (b *Bot) reply(chatID int64, text string) {
	msg := tgbotapi.NewMessage(chatID, text)
	b.api.Send(msg)
}
