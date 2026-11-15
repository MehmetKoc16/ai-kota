using System.Drawing;
using System.Drawing.Drawing2D;
using System.Runtime.InteropServices;

namespace KotaTepsi;

public static class SimgeCizici
{
    [DllImport("user32.dll", SetLastError = true)]
    private static extern bool DestroyIcon(IntPtr hIcon);

    public static Icon Ciz(KotaVerisi? veri)
    {
        using var bmp = new Bitmap(32, 32, System.Drawing.Imaging.PixelFormat.Format32bppArgb);
        using (var g = Graphics.FromImage(bmp))
        {
            g.SmoothingMode = SmoothingMode.AntiAlias;
            g.Clear(Color.Transparent);

            const float kalinlik = 5.0f;
            var halkaAlani = new RectangleF(4.0f, 4.0f, 24.0f, 24.0f);

            using var izKalem = new Pen(Color.FromArgb(140, 128, 128, 128), kalinlik)
            {
                StartCap = LineCap.Round,
                EndCap = LineCap.Round,
            };
            g.DrawArc(izKalem, halkaAlani, 0f, 360f);

            var kritik = Bicim.EnKritik(veri);
            if (kritik is not null)
            {
                double yuzde = Math.Clamp(kritik.Value.EnYuksekYuzde, 0.0, 100.0);
                float aci = (float)(360.0 * yuzde / 100.0);
                if (aci > 0.5f)
                {
                    Color renk = Bicim.EtiketRengi(kritik.Value.Saglayici.Etiket);
                    using var dolguKalem = new Pen(renk, kalinlik)
                    {
                        StartCap = LineCap.Round,
                        EndCap = LineCap.Round,
                    };
                    g.DrawArc(dolguKalem, halkaAlani, -90f, aci);
                }
            }
        }

        IntPtr hIcon = bmp.GetHicon();
        try
        {
            using var gecici = Icon.FromHandle(hIcon);
            return (Icon)gecici.Clone();
        }
        finally
        {
            DestroyIcon(hIcon);
        }
    }
}
