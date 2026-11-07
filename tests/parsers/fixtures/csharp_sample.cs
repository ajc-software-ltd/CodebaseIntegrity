// C# extraction fixture: namespaces, interfaces, classes, records, structs,
// enums, methods, ctors, properties, events, delegates, inheritance.

namespace Engine.Rendering
{
    public interface IRenderer
    {
        void Render();
    }

    public class Renderer : BaseRenderer, IRenderer
    {
        private int _frame;

        public Renderer()
        {
        }

        static Renderer()
        {
        }

        public void Render()
        {
        }

        public int Frame { get; set; }

        public event System.EventHandler FrameChanged;

        public delegate void FrameHandler(int frame);

        internal class RenderScope
        {
            public void Begin()
            {
            }
        }
    }

    public record RenderStats(int Frames);

    public struct RenderState
    {
        int mode;
    }

    public enum RenderMode
    {
        Solid,
        Wireframe
    }
}
