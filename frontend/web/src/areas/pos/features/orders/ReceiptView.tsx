import { formatINR } from '@shopdesk/shared';

import type { Receipt } from '../cart/api';

const PAYMENT = { cash: 'Cash', upi: 'UPI', card: 'Card' } as const;

/** 80mm thermal-style receipt (ui-context §4.4). `.receipt-print` is the only thing printed. */
export function ReceiptView({ receipt }: { receipt: Receipt }) {
  const { shop, order } = receipt;
  const when = new Date(order.created_at).toLocaleString('en-IN', {
    timeZone: 'Asia/Kolkata',
    dateStyle: 'short',
    timeStyle: 'short',
  });
  return (
    <div className="receipt-print mx-auto w-full max-w-[80mm] bg-white p-3 font-mono text-[12px] leading-snug text-black">
      <div className="text-center">
        <p className="text-sm font-bold">{shop.name}</p>
        {shop.address && <p>{shop.address}</p>}
        {shop.phone && <p>{shop.phone}</p>}
        {shop.gstin && <p>GSTIN {shop.gstin}</p>}
      </div>
      <hr className="my-2 border-dashed border-black" />
      <p>Invoice: {order.order_number}</p>
      <p>Date: {when}</p>
      <p>Customer: {order.customer_name}</p>
      {order.customer_phone && <p>Phone: {order.customer_phone}</p>}
      <p>Cashier: {order.cashier_name}</p>
      <hr className="my-2 border-dashed border-black" />
      <table className="w-full">
        <tbody>
          {order.lines.map((line) => (
            <tr key={line.code} className="align-top">
              <td className="pr-1">
                {line.name}
                <div>
                  {line.qty} × {formatINR(line.unit_price)}
                </div>
              </td>
              <td className="text-right whitespace-nowrap">{formatINR(line.line_total)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <hr className="my-2 border-dashed border-black" />
      <div className="flex justify-between">
        <span>Subtotal (MP)</span>
        <span>{formatINR(order.subtotal_mp)}</span>
      </div>
      {order.discount_applied && (
        <div className="flex justify-between">
          <span>Discount</span>
          <span>−{formatINR(order.discount_amount)}</span>
        </div>
      )}
      <div className="flex justify-between text-sm font-bold">
        <span>TOTAL</span>
        <span>{formatINR(order.total)}</span>
      </div>
      {order.payment_mode && <p>Payment: {PAYMENT[order.payment_mode]}</p>}
      <hr className="my-2 border-dashed border-black" />
      <p className="text-center">{shop.footer}</p>
    </div>
  );
}
