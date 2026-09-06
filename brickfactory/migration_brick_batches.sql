-- Runs transactionally on API startup, after the old process stops.
SELECT pg_advisory_xact_lock(624018);
CREATE TABLE IF NOT EXISTS brick_batch_state (id INT PRIMARY KEY CHECK(id=1), cutover_date DATE NOT NULL);
CREATE TABLE IF NOT EXISTS brick_batches (
 batch_id BIGSERIAL PRIMARY KEY,
 source TEXT NOT NULL CHECK(source IN ('opening','production','return','transfer')),
 production_date DATE,
 received_date DATE NOT NULL,
 received_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
 initial_quantity INT NOT NULL CHECK(initial_quantity>=0),
 remaining_quantity INT NOT NULL CHECK(remaining_quantity>=0 AND remaining_quantity<=initial_quantity),
 CHECK ((source='production' AND production_date IS NOT NULL) OR (source<>'production' AND production_date IS NULL))
);
CREATE UNIQUE INDEX IF NOT EXISTS brick_batches_production_day ON brick_batches(production_date) WHERE source='production';
CREATE UNIQUE INDEX IF NOT EXISTS brick_batches_opening ON brick_batches(source) WHERE source='opening';
CREATE TABLE IF NOT EXISTS brick_sale_allocations (
 sale_id INT NOT NULL REFERENCES brick_sales(sale_id),
 batch_id BIGINT NOT NULL REFERENCES brick_batches(batch_id),
 quantity INT NOT NULL CHECK(quantity>0),
 PRIMARY KEY(sale_id,batch_id)
);
CREATE TABLE IF NOT EXISTS brick_batch_movements (
 id BIGSERIAL PRIMARY KEY,
 batch_id BIGINT NOT NULL REFERENCES brick_batches(batch_id),
 quantity INT NOT NULL CHECK(quantity<>0),
 reason TEXT NOT NULL,
 sale_id INT REFERENCES brick_sales(sale_id),
 occurred_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
DO $$
DECLARE opening_total INT; sold_today INT; opening_id BIGINT; today DATE := (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Kolkata')::DATE;
BEGIN
 IF NOT EXISTS(SELECT 1 FROM brick_batch_state WHERE id=1) THEN
  LOCK TABLE outlet_stock, production_log, brick_sales, outlet_stock_adjustments IN EXCLUSIVE MODE;
  SELECT total_bricks INTO STRICT opening_total FROM outlet_stock WHERE id=1;
  IF opening_total<0 THEN RAISE EXCEPTION 'Opening stock is negative; reconcile before migration'; END IF;
  SELECT COALESCE(SUM(bricks_purchased),0) INTO sold_today FROM brick_sales WHERE sale_date=today;
  INSERT INTO brick_batches(source,received_date,initial_quantity,remaining_quantity)
   VALUES('opening',today,opening_total+sold_today,opening_total) RETURNING batch_id INTO opening_id;
  -- Same-day existing sales can still be corrected without inventing old production dates.
  INSERT INTO brick_sale_allocations(sale_id,batch_id,quantity)
   SELECT sale_id,opening_id,bricks_purchased FROM brick_sales WHERE sale_date=today;
  INSERT INTO brick_batch_state VALUES(1,today);
 END IF;
END $$;
