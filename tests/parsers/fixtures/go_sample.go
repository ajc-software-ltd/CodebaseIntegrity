// Go extraction fixture.
package render

type Renderer struct {
	Width int
}

type Drawable interface {
	Draw()
}

func (r *Renderer) Draw() {
}

func (r Renderer) Resize(w int) {
}

func New(width int) *Renderer {
	return &Renderer{Width: width}
}
