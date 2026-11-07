// TypeScript extraction fixture.
namespace App.Services {
    export interface IRenderer extends IBase {
        render(): void;
    }

    export abstract class Renderer implements IRenderer {
        private count: number;
        constructor() {}
        public render(): void {}
        public static build(): Renderer { return null; }
    }

    export enum Mode { Fast = 1, Slow }

    export type Callback = () => void;

    function configure(opts: string): void {}
}
