import React from 'react';
import { AlertOctagon, PhoneCall, Mail } from 'lucide-react';

interface CrisisBannerProps {
  escalateToHod: boolean;
  referToCounsellor: boolean;
}

export const CrisisBanner: React.FC<CrisisBannerProps> = ({
  escalateToHod,
  referToCounsellor,
}) => {
  if (!escalateToHod && !referToCounsellor) return null;

  return (
    <div className="rounded-2xl border border-rose-300 dark:border-rose-600/40 bg-rose-50 dark:bg-rose-950/30 p-5 shadow-soft animate-fade-up">
      <div className="flex items-start space-x-3.5">
        <div className="p-2 rounded-xl bg-rose-100 dark:bg-rose-600/20 text-rose-600 flex-shrink-0 mt-0.5">
          <AlertOctagon className="w-5 h-5" />
        </div>
        <div className="flex-1">
          <h4 className="text-sm font-bold text-rose-800 dark:text-rose-300">
            Priority Wellness & Mentorship Referral
          </h4>
          <p className="mt-1 text-xs text-rose-700 dark:text-rose-400 leading-relaxed">
            Indications of severe distress or potential crisis have triggered an immediate priority protocol.
            {escalateToHod && ' The Head of Department has been notified for administrative support.'}
          </p>

          <div className="mt-3 flex flex-wrap gap-4 pt-3 border-t border-rose-200 dark:border-rose-800/40 text-xs">
            <div className="flex items-center text-rose-800 dark:text-rose-300 font-semibold">
              <PhoneCall className="w-4 h-4 mr-1.5 text-rose-600" />
              <span>Campus Wellness Helpline: 1800-599-0019</span>
            </div>
            <div className="flex items-center text-rose-800 dark:text-rose-300 font-semibold">
              <Mail className="w-4 h-4 mr-1.5 text-rose-600" />
              <span>wellness.support@institution.edu</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
