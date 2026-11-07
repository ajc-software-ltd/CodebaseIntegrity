// Rust extraction fixture.
pub mod render {
    pub struct Renderer {
        pub width: u32,
    }

    pub trait Drawable {
        fn draw(&self);
    }

    impl Renderer {
        pub fn new() -> Renderer {
            Renderer { width: 0 }
        }
        pub fn resize(&mut self, w: u32) {}
    }

    impl Drawable for Renderer {
        fn draw(&self) {}
    }

    pub enum Mode {
        Fast,
        Slow,
    }

    pub fn helper(x: u32) -> u32 {
        x
    }
}
