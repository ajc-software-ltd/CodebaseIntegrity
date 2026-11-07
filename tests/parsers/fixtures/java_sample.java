// Java extraction fixture.
package com.example.render;

public class Renderer extends Base implements IRenderer {
    private int count;

    public Renderer() {
    }

    public void render(int mode) {
    }

    public static class Scope {
        public void begin() {
        }
    }
}

interface IRenderer {
    void render(int mode);
}
