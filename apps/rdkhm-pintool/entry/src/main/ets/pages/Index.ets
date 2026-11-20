import { request } from 'libpintool.so';
import { PIN_DATA, PinRecord } from '../common/PinData';

function payload(reply: string): string {
  const lines = reply.split('\n').filter((line: string) => line.length > 0 && line !== '.');
  if (lines.length > 0 && lines[0].startsWith('ERR')) {
    throw new Error(lines.join(' '));
  }
  return lines.slice(1).join('\n');
}

@Entry
@Component
struct Index {
  @State pins: PinRecord[] = PIN_DATA;
  @State status: string = 'loading';
  @State output: string = '';
  private started: boolean = false;

  onPageShow(): void {
    if (this.started) {
      return;
    }
    this.started = true;
    try {
      const reply = request('ping');
      if (reply.indexOf('PONG') < 0) {
        throw new Error(reply);
      }
      this.status = 'GPIO service connected';
    } catch (error) {
      this.status = 'GPIO service unavailable: ' + String(error);
    }
  }

  private run(command: string): void {
    try {
      this.output = command + '\n' + payload(request(command));
    } catch (error) {
      this.output = command + '\n' + String(error);
    }
  }

  private readPin(pin: number): void {
    this.run('export ' + pin + ' in');
    this.run('get ' + pin);
  }

  build() {
    Column({ space: 8 }) {
      Row() {
        Text('RDK PinTool').fontSize(24).fontWeight(FontWeight.Bold)
        Blank()
        Text(this.status).fontSize(11).fontColor('#666666')
      }.width('100%')

      List({ space: 4 }) {
        ForEach(this.pins, (pin: PinRecord) => {
          ListItem() {
            Column({ space: 4 }) {
              Row({ space: 8 }) {
                Text('PIN ' + pin.physical_pin).fontSize(16).width(62)
                Text('GPIO ' + pin.gpio).fontSize(14).width(86)
                Text(pin.soc_name).fontSize(14).layoutWeight(1)
                Text(pin.usable_as_gpio ? 'usable' : 'busy')
                  .fontSize(13)
                  .fontColor(pin.usable_as_gpio ? '#1A7F37' : '#B42318')
              }.width('100%')

              if (pin.usable_as_gpio) {
                Row({ space: 6 }) {
                  Button('Read').fontSize(12).height(28)
                    .onClick(() => { this.readPin(pin.physical_pin); })
                  Button('High').fontSize(12).height(28)
                    .onClick(() => { this.run('export ' + pin.physical_pin + ' out 1'); })
                  Button('Low').fontSize(12).height(28)
                    .onClick(() => { this.run('export ' + pin.physical_pin + ' out 0'); })
                  Button('Input').fontSize(12).height(28)
                    .onClick(() => { this.run('export ' + pin.physical_pin + ' in'); })
                  Button('Release').fontSize(12).height(28)
                    .onClick(() => { this.run('unexport ' + pin.physical_pin); })
                }.width('100%')
              } else {
                Text(pin.note).fontSize(12).fontColor('#B42318')
              }
            }.width('100%').padding(6)
          }
        }, (pin: PinRecord) => pin.physical_pin.toString())
      }.layoutWeight(1).width('100%')

      Scroll() {
        Text(this.output).fontSize(12).width('100%').textAlign(TextAlign.Start)
      }.height(110).width('100%').backgroundColor('#F5F5F5').padding(6)
    }.padding(12).width('100%').height('100%').backgroundColor('#FFFFFF')
  }
}
