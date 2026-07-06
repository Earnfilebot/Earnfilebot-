from asyncpg import Pool, Connection, Record


class PurchaseRepository:

    @staticmethod
    async def get_file(
        conn: Connection,
        code: str
    ) -> Record | None:

        return await conn.fetchrow(
            """
            SELECT
                owner_id,
                price,
                is_paid
            FROM files
            WHERE code=$1
            """,
            code
        )

    @staticmethod
    async def get_latest_purchase(
        conn: Connection,
        user_id: int,
        file_code: str
    ) -> Record | None:

        return await conn.fetchrow(
            """
            SELECT *
            FROM file_purchases
            WHERE user_id=$1
              AND file_code=$2
            ORDER BY id DESC
            LIMIT 1
            """,
            user_id,
            file_code
        )

    @staticmethod
    async def get_purchase_by_invoice(
        conn: Connection,
        invoice_id: str
    ) -> Record | None:

        return await conn.fetchrow(
            """
            SELECT *
            FROM file_purchases
            WHERE payment_id=$1
            """,
            invoice_id
        )

    @staticmethod
    async def create_purchase(
        conn: Connection,
        *,
        user_id: int,
        owner_id: int,
        file_code: str,
        price: int,
        invoice_id: str,
    ):

        await conn.execute(
            """
            INSERT INTO file_purchases
            (
                user_id,
                file_code,
                owner_id,
                paid_price,
                payment_id,
                status,
                created_at
            )
            VALUES
            (
                $1,$2,$3,$4,$5,
                'pending',
                NOW()
            )
            ON CONFLICT (payment_id)
            DO UPDATE
            SET
                status='pending'
            """,
            user_id,
            file_code,
            owner_id,
            price,
            invoice_id
        )

    @staticmethod
    async def update_qr_message(
        conn: Connection,
        invoice_id: str,
        chat_id: int,
        message_id: int
    ):

        await conn.execute(
            """
            UPDATE file_purchases
            SET
                qr_chat_id=$1,
                qr_message_id=$2
            WHERE payment_id=$3
            """,
            chat_id,
            message_id,
            invoice_id
        )

    @staticmethod
    async def mark_paid(
        conn: Connection,
        invoice_id: str
    ):

        await conn.execute(
            """
            UPDATE file_purchases
            SET status='paid'
            WHERE payment_id=$1
            """,
            invoice_id
        )

    @staticmethod
    async def mark_expired(
        conn: Connection,
        invoice_id: str
    ):

        await conn.execute(
            """
            UPDATE file_purchases
            SET status='expired'
            WHERE payment_id=$1
            """,
            invoice_id
        )

    @staticmethod
    async def mark_cancelled(
        conn: Connection,
        invoice_id: str
    ):

        await conn.execute(
            """
            UPDATE file_purchases
            SET status='cancelled'
            WHERE payment_id=$1
            """,
            invoice_id
        )

    @staticmethod
    async def delete_purchase(
        conn: Connection,
        invoice_id: str
    ):

        await conn.execute(
            """
            DELETE FROM file_purchases
            WHERE payment_id=$1
            """,
            invoice_id
        )
