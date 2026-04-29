/**
 * Built-in demo transactions for one-click showcase.
 *
 * Four users with different behavioral patterns:
 *   usr_0041 — normal flow then two large spikes (anomaly)
 *   usr_0127 — consistently small, stable (clean)
 *   usr_0203 — mid-range with one spike in the middle (anomaly)
 *   usr_0088 — high but stable amounts (clean)
 */
const DEMO_TRANSACTIONS = [
  { user_id: "usr_0041", amount: 120.0,  transaction_time: "2024-03-10T09:15:00" },
  { user_id: "usr_0041", amount: 135.5,  transaction_time: "2024-03-10T10:30:00" },
  { user_id: "usr_0041", amount: 110.0,  transaction_time: "2024-03-10T14:20:00" },
  { user_id: "usr_0041", amount: 8500.0, transaction_time: "2024-03-10T14:45:00" },
  { user_id: "usr_0041", amount: 7200.0, transaction_time: "2024-03-10T15:01:00" },

  { user_id: "usr_0127", amount: 45.0,   transaction_time: "2024-03-10T08:00:00" },
  { user_id: "usr_0127", amount: 52.0,   transaction_time: "2024-03-10T09:00:00" },
  { user_id: "usr_0127", amount: 48.0,   transaction_time: "2024-03-10T11:30:00" },
  { user_id: "usr_0127", amount: 55.0,   transaction_time: "2024-03-10T13:00:00" },

  { user_id: "usr_0203", amount: 300.0,  transaction_time: "2024-03-10T07:00:00" },
  { user_id: "usr_0203", amount: 320.0,  transaction_time: "2024-03-10T08:30:00" },
  { user_id: "usr_0203", amount: 310.0,  transaction_time: "2024-03-10T10:00:00" },
  { user_id: "usr_0203", amount: 1950.0, transaction_time: "2024-03-10T10:05:00" },
  { user_id: "usr_0203", amount: 290.0,  transaction_time: "2024-03-10T12:00:00" },

  { user_id: "usr_0088", amount: 500.0,  transaction_time: "2024-03-10T06:00:00" },
  { user_id: "usr_0088", amount: 510.0,  transaction_time: "2024-03-10T08:00:00" },
  { user_id: "usr_0088", amount: 490.0,  transaction_time: "2024-03-10T10:00:00" },
  { user_id: "usr_0088", amount: 520.0,  transaction_time: "2024-03-10T12:00:00" },
  { user_id: "usr_0088", amount: 505.0,  transaction_time: "2024-03-10T14:00:00" },
  { user_id: "usr_0088", amount: 515.0,  transaction_time: "2024-03-10T16:00:00" },
];

export default DEMO_TRANSACTIONS;
