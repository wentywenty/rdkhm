import Ability from '@ohos.app.ability.UIAbility';
import window from '@ohos.window';

export default class EntryAbility extends Ability {
  onWindowStageCreate(windowStage: window.WindowStage): void {
    windowStage.loadContent('pages/Index', (error) => {
      if (error.code) {
        console.error('RDK PinTool loadContent failed: ' + JSON.stringify(error));
      }
    });
  }
}
