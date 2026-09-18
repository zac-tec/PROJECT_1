import unittest
from unittest.mock import MagicMock, patch
from datetime import date
from batch_stock import available_for_sale, allocate_sale
from fastapi import HTTPException
from schemas import BrickSaleRequest

class DatedStockTests(unittest.TestCase):
    def test_later_replenishment_cannot_fund_earlier_sale(self):
        c=MagicMock()
        c.fetchall.side_effect=[
            [{'batch_id':1,'remaining_quantity':100}],
            [{'quantity':80},{'quantity':-30}],
        ]
        with patch('batch_stock.factory_today',return_value=date(2026,9,19)):
            rows=available_for_sale(c,date(2026,9,17))
        self.assertEqual(rows[0]['remaining_quantity'],20)
        params=c.execute.call_args_list[0].args[1]
        self.assertEqual(params,(date(2026,9,17),date(2026,9,10)))

    def test_later_sales_remain_reserved(self):
        c=MagicMock();c.fetchall.side_effect=[[{'batch_id':1,'remaining_quantity':50}],[{'quantity':-100}]]
        with patch('batch_stock.factory_today',return_value=date(2026,9,19)):
            self.assertEqual(available_for_sale(c,date(2026,9,17))[0]['remaining_quantity'],50)

    def test_insufficient_dated_stock_does_not_write(self):
        c=MagicMock()
        with patch('batch_stock.available_for_sale',return_value=[{'remaining_quantity':3}]):
            with self.assertRaises(HTTPException) as e:allocate_sale(c,1,4,date(2026,9,17))
        self.assertEqual(e.exception.status_code,409);c.execute.assert_not_called()

    def test_sale_date_optional_for_old_clients(self):
        body=BrickSaleRequest(customer_name='Test',bricks_purchased=1,cost_per_brick=8.4,amount_paid=0)
        self.assertIsNone(body.sale_date)
        body=BrickSaleRequest(customer_name='Test',sale_date='2026-09-17',bricks_purchased=1,cost_per_brick=8.4,amount_paid=0)
        self.assertEqual(body.sale_date,date(2026,9,17))
