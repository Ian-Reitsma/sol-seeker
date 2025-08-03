pub enum Event {
    Liquidity { delta: f64, prev: f64 },
    Swap { amount: f64, timestamp_ms: i64 },
    // Additional event variants can be added here as new features require.
    Flush { ack: crossbeam_channel::Sender<()> },
}
